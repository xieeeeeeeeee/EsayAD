"""Strict adapter around the pinned MIT converter; create new libraries only."""
import contextlib
import copy
from dataclasses import dataclass
import io
import json
import math
import re
from pathlib import Path
import sys
import uuid

from .catalog import normalize_id, save_json

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(ROOT / 'vendor' / 'jlc2ad'))
from jlc2ad_core.footprint_parser import FootprintParser
from jlc2ad_core.schematic_parser import SchematicParser
from jlc2ad_core.pcb_writer import PcbLibWriter
from jlc2ad_core.sch_writer import SchLibWriter
from jlc2ad_core.writer_common import _safe_storage_name, _write_cstring_param_block
from jlc2ad_core.types import Region, LAYER_MAP


class ConversionError(RuntimeError):
    pass


class SourceWriter(SchLibWriter):
    def _build_component_data(self, sym, storage_name):
        data = super()._build_component_data(sym, storage_name)
        for name, value in [('Source URL', sym.source_url), ('Library Source', 'JLCEDA/EasyEDA Official Library'),
                            ('JLCEDA', 'https://lceda.cn/'), ('EasyEDA', 'https://easyeda.com/')]:
            data += _write_cstring_param_block({'RECORD': '41', 'OwnerIndex': '0', 'OwnerPartId': '-1',
                                                'FontID': '2', 'IsHidden': 'T', 'Name': name, 'Text': value})
        return data


@dataclass
class ExportResult:
    lcsc: str
    schlib: Path
    pcblib: Path
    manifest: Path
    symbol: object
    footprint: object
    pin_numbers: list[str]
    pad_numbers: list[str]
    warnings: list[str]


def normalize_component(lcsc: str, raw: dict) -> dict:
    sch = raw.get('dataStr')
    package = raw.get('packageDetail')
    if not isinstance(sch, dict) or not isinstance(package, dict) or not package.get('dataStr'):
        raise ConversionError('该元件没有完整的原理图符号与 PCB 封装')
    if not isinstance(package['dataStr'], dict):
        raise ConversionError('暂不支持该版本封装数据')
    if not isinstance(sch.get('shape'), list) or not isinstance(package['dataStr'].get('shape'), list):
        raise ConversionError('模型图元列表缺失')
    sch = copy.deepcopy(sch)
    for index, shape in enumerate(sch['shape']):
        if not shape.startswith('P~'):
            continue
        sections = shape.split('^^')
        header = sections[0].split('~')
        if len(header) < 7:
            raise ConversionError('引脚头数据不完整')
        # The header carries the SPICE ordinal. Section 4 carries the physical
        # pin designator printed on the symbol and matched to footprint pads.
        if len(sections) > 4:
            number_fields = sections[4].split('~')
            if len(number_fields) > 4 and number_fields[4].strip():
                header[3] = number_fields[4].strip()
        if not header[6].strip():
            header[6] = '0'
        sections[0] = '~'.join(header)
        sch['shape'][index] = '^^'.join(sections)
    para = sch.get('head', {}).get('c_para', {})
    if sch.get('subparts') or sch.get('head', {}).get('subpart') or any(s.startswith('LIB~') for s in sch['shape']):
        raise ConversionError('初版暂不支持多单元符号')
    return {'lcsc_id': lcsc, 'title': raw.get('title') or lcsc, 'description': raw.get('description') or '',
            'sch_dataStr': sch, 'dataStr': package, 'package_name': package.get('title') or para.get('package') or lcsc,
            'designator': para.get('pre') or 'U?', 'value': para.get('Value') or '',
            'manufacturer': para.get('Manufacturer') or '',
            'manufacturer_part': para.get('Manufacturer Part') or raw.get('title') or lcsc,
            'supplier_part': lcsc, 'supplier': 'LCSC', 'attributes': para,
            'url': (raw.get('lcsc') or {}).get('url') or f'https://www.lcsc.com/search?q={lcsc}'}


def validate_shapes(data: dict) -> list[str]:
    warnings = []
    for scope, shapes, supported in [
        ('符号', data['sch_dataStr']['shape'], {'P', 'R', 'PL', 'PG', 'E', 'A', 'PT'}),
        ('封装', data['dataStr']['dataStr']['shape'], {'PAD', 'TRACK', 'RECT', 'FILL', 'ARC', 'CIRCLE', 'POLY', 'SOLIDREGION'})]:
        for shape in shapes:
            fields = shape.split('~')
            kind = fields[0]
            if kind in {'T', 'TEXT', 'SVGNODE'}:
                warning = f'{scope}的文字/3D 图元未转换；需要在 AD 核对文字标记与极性'
                if warning not in warnings:
                    warnings.append(warning)
                continue
            if kind not in supported:
                raise ConversionError(f'暂不支持{scope}图元 {kind}，已阻止不完整导出')
            if kind == 'SOLIDREGION':
                if len(fields) > 4 and fields[1] in {'99', '100', '101'} and fields[4] == 'cutout':
                    warnings.append('外观层的挖空未转换；不影响电气焊盘，需核对外观')
                    continue
                if len(fields) < 5 or fields[4] != 'solid' or int(fields[1]) not in LAYER_MAP:
                    raise ConversionError('暂不支持该区域或挖空类型')
                if re.search(r'[A-Za-z]', re.sub(r'[MLZ]', '', fields[3])):
                    raise ConversionError('暂不支持曲线区域')
            if kind == 'PAD':
                if len(fields) < 16 or fields[1] not in {'RECT', 'ELLIPSE', 'OVAL'}:
                    raise ConversionError('初版暂不支持自定义多边形焊盘')
                try:
                    hole_length = float(fields[13].strip() or '0')
                except ValueError as exc:
                    raise ConversionError('焊盘孔长数据无效，已阻止导出') from exc
                if not math.isfinite(hole_length) or hole_length < 0:
                    raise ConversionError('焊盘孔长数据无效，已阻止导出')
                if hole_length > 0 or fields[14].strip():
                    raise ConversionError('初版暂不支持槽孔焊盘')
                if fields[6] not in ('1', '2', '11'):
                    raise ConversionError('暂不支持该焊盘层')
    return warnings


class Exporter:
    def __init__(self, output: Path):
        self.output = Path(output)

    def parse(self, lcsc: str, raw: dict):
        lcsc = normalize_id(lcsc)
        data = normalize_component(lcsc, raw)
        warnings = validate_shapes(data)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            symbol = SchematicParser().parse(data)
            footprint = FootprintParser().parse(data)
        head = data['dataStr']['dataStr'].get('head', {})
        ox, oy = float(head.get('x', 0)), float(head.get('y', 0))
        for shape in data['dataStr']['dataStr']['shape']:
            fields = shape.split('~')
            if fields[0] == 'SOLIDREGION' and fields[4] == 'solid':
                numbers = [float(n) for n in re.findall(r'-?\d+(?:\.\d+)?', fields[3])]
                if len(numbers) < 6 or len(numbers) % 2:
                    raise ConversionError('区域顶点数据不完整')
                points = [(round((x - ox) * 100000), -round((y - oy) * 100000)) for x, y in zip(numbers[::2], numbers[1::2])]
                if points[0] != points[-1]:
                    points.append(points[0])
                footprint.regions.append(Region(points=points, layer=LAYER_MAP[int(fields[1])]))
        if output.getvalue().strip():
            raise ConversionError(f'图元解析失败，已阻止导出：{output.getvalue().strip()}')
        if not symbol or not symbol.pins or not footprint.pads:
            raise ConversionError('符号没有引脚或封装没有焊盘')
        source_pins = [s.split('~')[3] for s in data['sch_dataStr']['shape'] if s.startswith('P~')]
        source_pads = [s.split('~')[8] for s in data['dataStr']['dataStr']['shape'] if s.startswith('PAD~')]
        if len(source_pins) != len(symbol.pins) or len(source_pads) != len(footprint.pads):
            raise ConversionError('转换后的引脚或焊盘数量与来源不一致')
        if set(source_pins) != set(source_pads):
            raise ConversionError(f'引脚与焊盘编号不匹配：{source_pins} / {source_pads}')
        if len(source_pins) != len(set(source_pins)):
            raise ConversionError('初版暂不支持重复编号/多单元符号')
        # Names are unique across parts and fit the Altium OLE 31-character storage limit.
        symbol.name = lcsc
        footprint.name = lcsc + '_FP'
        footprint.model_3d = None
        symbol.package = footprint.name
        for obj in (symbol, footprint):
            for key in ('manufacturer', 'manufacturer_part', 'value', 'supplier_part', 'supplier'):
                setattr(obj, key, data[key])
        symbol.source_url = data['url']
        return symbol, footprint, sorted(source_pins), sorted(source_pads), warnings

    def export(self, lcsc: str, raw: dict) -> ExportResult:
        lcsc = normalize_id(lcsc)
        symbol, footprint, pins, pads, warnings = self.parse(lcsc, raw)
        folder = self.output / lcsc / uuid.uuid4().hex[:12]
        folder.mkdir(parents=True, exist_ok=False)
        schlib, pcblib = folder / f'{lcsc}.SchLib', folder / f'{lcsc}.PcbLib'
        SourceWriter().write(str(schlib), [symbol])
        PcbLibWriter().write(str(pcblib), [footprint])
        import olefile
        for file, name in ((schlib, symbol.name), (pcblib, footprint.name)):
            with olefile.OleFileIO(str(file)) as lib:
                if not lib.exists([name, 'Data']):
                    raise ConversionError('生成的库缺少元件数据流')
        manifest = folder / 'manifest.json'
        save_json(folder / 'source.json', raw)
        save_json(manifest, {'state': 'generated', 'lcsc': lcsc, 'symbol': symbol.name, 'footprint': footprint.name,
                            'pin_numbers': pins, 'pad_numbers': pads, 'warnings': warnings,
                            'schlib': str(schlib), 'pcblib': str(pcblib),
                            'source': '嘉立创EDA/EasyEDA官方库', 'source_url': symbol.source_url,
                            'converter': 'NatsumiAi/jlc2ad@7bb2d0f83790430d9aae892ecc2f67755c348b9d'})
        return ExportResult(lcsc, schlib, pcblib, manifest, symbol, footprint, pins, pads, warnings)
