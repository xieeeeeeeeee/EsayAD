from pathlib import Path
from contextlib import contextmanager
import msvcrt
import subprocess
import uuid

from .catalog import save_json


class BridgeBusyError(RuntimeError):
    pass


def pascal_string(text: str) -> str:
    tokens, chars = [], ''
    for char in str(text):
        if 32 <= ord(char) < 127:
            chars += char.replace("'", "''")
        else:
            if chars:
                tokens.append("'" + chars + "'")
                chars = ''
            for offset in range(0, len(char.encode('utf-16-le')), 2):
                tokens.append('#' + str(int.from_bytes(char.encode('utf-16-le')[offset:offset+2], 'little')))
    if chars:
        tokens.append("'" + chars + "'")
    return ''.join(tokens) or "''"


def read_receipt(project: Path) -> str:
    # Only stat immutable markers. Opening a shared receipt can race Delphi's
    # exclusive SaveToFile handle and leave AD stopped inside an I/O exception.
    for state in ('failed', 'placed', 'cancelled', 'no_schematic', 'placing', 'opened'):
        if (project.parent / (state + '.state')).is_file():
            return state
    return 'pending'


class Bridge:
    def __init__(self, data_root: Path, altium=Path(r'E:\AD24\X2.EXE')):
        self.root = Path(data_root).resolve()
        self.altium = Path(altium)
        self.lock = self.root / 'import.lock'

    @contextmanager
    def _transaction(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / 'import.guard').open('a+b') as guard:
            guard.seek(0, 2)
            if guard.tell() == 0:
                guard.write(b'0')
                guard.flush()
            guard.seek(0)
            try:
                msvcrt.locking(guard.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise BridgeBusyError('另一个助手正在处理 AD 请求，请稍候') from exc
            try:
                yield
            finally:
                guard.seek(0)
                msvcrt.locking(guard.fileno(), msvcrt.LK_UNLCK, 1)

    def active_project(self):
        with self._transaction():
            return self._active_project()

    def _active_project(self):
        try:
            content = self.lock.read_text(encoding='utf-8').strip()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise BridgeBusyError('另一个助手正在提交 AD 请求，请稍候') from exc
        if not content:
            raise BridgeBusyError('另一个助手正在提交 AD 请求，请稍候')
        project = Path(content)
        if (project.parent / 'finished.state').is_file():
            self.lock.unlink(missing_ok=True)
            return None
        return project

    def reset_after_ad_stopped(self):
        """Manual recovery only: caller must first stop the AD script."""
        with self._transaction():
            self.lock.unlink(missing_ok=True)

    def prepare(self, result) -> Path:
        for path in (result.schlib, result.pcblib):
            if not path.resolve().is_relative_to(self.root) or not path.is_file():
                raise ValueError('只允许导入助手数据目录内已生成的库')
        folder = self.root / 'requests' / uuid.uuid4().hex
        folder.mkdir(parents=True)
        stem = 'Import_' + folder.name[:8]
        project, script = folder / f'{stem}.PrjScr', folder / f'{stem}.pas'
        template = '''procedure WriteState(Value : String);
var Lines : TStringList; Marker : String;
begin
  Lines := TStringList.Create;
  try
    try
      Marker := @RECEIPT_DIR@ + Value + '.state';
      Lines.Add(Value);
      Lines.SaveToFile(Marker + '.writing');
      RenameFile(Marker + '.writing', Marker);
    except
      { Status errors must never leave the AD script stopped in the debugger. }
    end;
  finally
    Lines.Free;
  end;
end;

function CountParts(Sheet : ISch_Document) : Integer;
var It : ISch_Iterator; Part : ISch_Component;
begin
  Result := 0;
  It := Sheet.SchIterator_Create;
  try
    It.AddFilter_ObjectSet(MkSet(eSchComponent));
    Part := It.FirstSchObject;
    while Part <> Nil do
    begin
      Result := Result + 1;
      Part := It.NextSchObject;
    end;
  finally
    Sheet.SchIterator_Destroy(It);
  end;
end;

procedure DoImportPart;
var Sheet : ISch_Document; BeforeCount : Integer; Ok : Boolean;
begin
  try
    IntegratedLibraryManager.InstallLibrary(@PCBLIB@);
    IntegratedLibraryManager.InstallLibrary(@SCHLIB@);
    WriteState('opened');
    Sheet := SchServer.GetCurrentSchDocument;
    if Sheet = Nil then
    begin
      WriteState('no_schematic');
      Exit;
    end;
    if UpperCase(ExtractFileExt(Sheet.DocumentName)) <> '.SCHDOC' then
    begin
      WriteState('no_schematic');
      Exit;
    end;
    BeforeCount := CountParts(Sheet);
    WriteState('placing');
    Ok := IntegratedLibraryManager.PlaceLibraryComponent(@SYMBOL@, @SCHLIB@, '');
    if CountParts(Sheet) > BeforeCount then WriteState('placed')
    else WriteState('cancelled');
    Sheet.GraphicallyInvalidate;
  except
    WriteState('failed');
  end;
end;

procedure ImportPart;
begin
  try
    DoImportPart;
  finally
    WriteState('finished');
  end;
end;
'''
        for key, value in {'RECEIPT_DIR': str(folder) + '\\', 'PCBLIB': result.pcblib.resolve(),
                           'SCHLIB': result.schlib.resolve(), 'SYMBOL': result.symbol.name}.items():
            template = template.replace('@' + key + '@', pascal_string(str(value)))
        script.write_text(template, encoding='ascii')
        project.write_text('[Design]\nVersion=1.0\n[Document1]\nDocumentPath=' + script.name + '\n', encoding='ascii')
        save_json(folder / 'request.json', {'state': 'prepared', 'lcsc': result.lcsc,
                                           'schlib': str(result.schlib), 'pcblib': str(result.pcblib)})
        return project

    def launch(self, project: Path):
        if not self.altium.is_file():
            raise FileNotFoundError(f'找不到 AD：{self.altium}')
        with self._transaction():
            if self._active_project() is not None:
                raise BridgeBusyError('AD 导入尚未结束。请在 AD 完成或取消放置，不要重复运行脚本。')
            try:
                with self.lock.open('x', encoding='utf-8') as stream:
                    stream.write(str(project.resolve()))
            except FileExistsError as exc:
                raise BridgeBusyError('另一个助手已有 AD 导入请求') from exc
            argument = f'-RScriptingSystem:RunScript(ProjectName={project}|ProcName={project.stem}>ImportPart)'
            try:
                subprocess.Popen([str(self.altium), argument], cwd=str(project.parent))
            except OSError:
                self.lock.unlink(missing_ok=True)
                raise
        return 'sent'
