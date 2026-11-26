"""Catalog search and success-only model cache; no account credentials needed."""
from dataclasses import dataclass
import json
from pathlib import Path
import re
import urllib.error
import urllib.request


class ServiceError(RuntimeError):
    pass


def normalize_id(value: str) -> str:
    value = value.strip().upper()
    if not re.fullmatch(r'C[1-9][0-9]*', value):
        raise ValueError('立创料号应为 C 加数字，例如 C25804')
    return value


def request_json(url: str, payload=None) -> dict:
    headers = {'User-Agent': 'LCSC-AD24-Assistant/0.1', 'Accept': 'application/json'}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode('utf-8')
        headers.update({'Content-Type': 'application/json', 'Referer': 'https://jlcpcb.com/parts'})
    request = urllib.request.Request(url, data=body, headers=headers)
    try:
        proxies = urllib.request.getproxies()
        # Windows commonly exposes a single system HTTP proxy for both protocols.
        if proxies.get('http') and not proxies.get('https'):
            proxies['https'] = proxies['http']
        opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
        with opener.open(request, timeout=25) as response:
            result = json.loads(response.read().decode('utf-8'))
        if not isinstance(result, dict):
            raise ValueError('JSON root is not an object')
        return result
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise ServiceError(f'网络请求失败或服务返回了非 JSON 内容：{exc}') from exc


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


@dataclass(frozen=True)
class Part:
    lcsc: str
    model: str = ''
    manufacturer: str = ''
    package: str = ''
    description: str = ''
    url: str = ''
    has_model: bool | None = None


@dataclass
class SearchPage:
    parts: list[Part]
    total: int
    page: int
    source: str = '嘉立创 JLCPCB 贴片元件目录（非立创商城全量目录）'


def parse_search(payload: dict, page: int) -> SearchPage:
    info = (payload.get('data') or {}).get('componentPageInfo')
    if payload.get('code') != 200 or not isinstance(info, dict) or not isinstance(info.get('list'), list):
        raise ServiceError(f'搜索服务返回异常：{payload.get("message") or "缺少结果列表"}')
    parts = []
    for item in info['list']:
        try:
            lcsc = normalize_id(str(item.get('componentCode', '')))
        except ValueError:
            continue
        parts.append(Part(lcsc, item.get('componentModelEn') or '', item.get('componentBrandEn') or '',
                          item.get('componentSpecificationEn') or '', item.get('describe') or '',
                          item.get('lcscGoodsUrl') or f'https://www.lcsc.com/search?q={lcsc}'))
    return SearchPage(parts, int(info.get('total') or 0), page)


class Catalog:
    def __init__(self, cache: Path, transport=request_json):
        self.cache = Path(cache)
        self.transport = transport

    def component(self, lcsc: str, refresh=False) -> dict:
        lcsc = normalize_id(lcsc)
        path = self.cache / f'{lcsc}.json'
        if not refresh and path.exists():
            try:
                cached = json.loads(path.read_text(encoding='utf-8'))
                if isinstance(cached, dict) and cached.get('title') and cached.get('dataStr'):
                    return cached
            except (ValueError, OSError):
                pass
        payload = self.transport(f'https://easyeda.com/api/products/{lcsc}/components')
        result = payload.get('result')
        if payload.get('success') is not True or not isinstance(result, dict) or not result.get('title'):
            raise ServiceError(f'{lcsc} 未找到可用的 EDA 模型（商品可能仍存在）')
        if not result.get('dataStr'):
            raise ServiceError(f'{lcsc} 缺少原理图模型')
        save_json(path, result)
        return result

    def search(self, query: str, page=1) -> SearchPage:
        query = query.strip()
        if not query or len(query) > 120 or page < 1:
            raise ValueError('请输入 1–120 个字符的型号、关键词或立创料号')
        if re.fullmatch(r'[cC][1-9][0-9]*', query):
            lcsc = normalize_id(query)
            raw = self.component(lcsc)
            para = (raw.get('dataStr') or {}).get('head', {}).get('c_para', {})
            part = Part(lcsc, raw['title'], para.get('Manufacturer', ''), para.get('package', ''),
                        raw.get('description', ''), (raw.get('lcsc') or {}).get('url', ''),
                        bool(raw.get('dataStr') and raw.get('packageDetail')))
            return SearchPage([part] if page == 1 else [], 1, page, '立创料号精确查询 / EasyEDA 官方库')
        payload = {'keyword': query, 'currentPage': page, 'pageSize': 20}
        return parse_search(self.transport('https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList', payload), page)
