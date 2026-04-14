// excel-copy VSCode Extension
// 선택한 텍스트를 HTML <table> 형식으로 클립보드에 올려서
// 사내 메신저(Slack, Teams 등)에 붙여넣을 때 표로 인식되게 합니다.

const vscode = require('vscode');
const os = require('os');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execSync } = require('child_process');

// ──────────────────────────────────────────────
// 1. 익스텐션 진입점
// ──────────────────────────────────────────────
function activate(context) {
    const cmd = vscode.commands.registerCommand('excelCopy.copyAsTable', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('열린 에디터가 없습니다.');
            return;
        }
        if (editor.selection.isEmpty) {
            vscode.window.showWarningMessage('먼저 텍스트를 선택하세요.');
            return;
        }

        const rawText = editor.document.getText(editor.selection);
        if (!rawText.trim()) {
            vscode.window.showWarningMessage('선택된 텍스트가 비어 있습니다.');
            return;
        }

        // 줄 → 행, 탭 → 열 로 파싱
        const lines = rawText.split(/\r?\n/);
        // 마지막 빈 줄 제거
        if (lines.length && lines[lines.length - 1].trim() === '') lines.pop();

        const rows = lines.map(line => line.split('\t'));
        const colCount = Math.max(...rows.map(r => r.length));

        const htmlTable = buildHtmlTable(rows);
        const tsv = rows.map(r => r.join('\t')).join('\n');

        try {
            setClipboardWithHtml(htmlTable, tsv);
            vscode.window.showInformationMessage(
                `✅ ${rows.length}행 × ${colCount}열 표 형식으로 복사됨! (Ctrl+V 로 붙여넣기)`
            );
        } catch (err) {
            vscode.window.showErrorMessage(
                `클립보드 복사 실패: ${err.message}\n` +
                (os.platform() === 'linux' ? '(Linux는 xclip 설치 필요: sudo apt install xclip)' : '')
            );
        }
    });

    context.subscriptions.push(cmd);
}

function deactivate() {}

// ──────────────────────────────────────────────
// 2. HTML <table> 생성
// ──────────────────────────────────────────────
function buildHtmlTable(rows) {
    const style = [
        'border-collapse:collapse',
        'font-family:sans-serif',
        'font-size:14px',
    ].join(';');

    const tdStyle = [
        'border:1px solid #d0d0d0',
        'padding:6px 10px',
        'white-space:pre',
    ].join(';');

    const trs = rows.map((cells, ri) => {
        const bg = ri % 2 === 0 ? '#ffffff' : '#f5f5f5';
        const tds = cells
            .map(cell => `<td style="${tdStyle};background:${bg}">${escHtml(cell)}</td>`)
            .join('');
        return `<tr>${tds}</tr>`;
    }).join('');

    return `<table style="${style}">${trs}</table>`;
}

function escHtml(str) {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ──────────────────────────────────────────────
// 3. 플랫폼별 클립보드 쓰기
//    핵심: text/plain 과 text/html 을 동시에 올린다
// ──────────────────────────────────────────────
function setClipboardWithHtml(tableHtml, plain) {
    const platform = os.platform();
    const id = crypto.randomBytes(4).toString('hex');
    const tmp = os.tmpdir();

    const htmlFile  = path.join(tmp, `excel_copy_${id}.html`);
    const plainFile = path.join(tmp, `excel_copy_${id}.txt`);
    fs.writeFileSync(htmlFile,  tableHtml, 'utf8');
    fs.writeFileSync(plainFile, plain,     'utf8');

    try {
        if (platform === 'darwin')      { macSetClipboard(htmlFile, plainFile, id, tmp); }
        else if (platform === 'win32')  { winSetClipboard(htmlFile, plainFile, id, tmp, tableHtml, plain); }
        else                            { linuxSetClipboard(htmlFile); }
    } finally {
        cleanup([htmlFile, plainFile]);
    }
}

// ── macOS: osascript (JXA) ──────────────────
function macSetClipboard(htmlFile, plainFile, id, tmp) {
    const jxaFile = path.join(tmp, `excel_copy_${id}.js`);

    // JXA로 NSPasteboard에 HTML + 일반텍스트 동시 등록
    const jxa = `
ObjC.import('Foundation');
ObjC.import('AppKit');

var htmlPath  = ${JSON.stringify(htmlFile)};
var plainPath = ${JSON.stringify(plainFile)};

function readUTF8(p) {
    var ns = $.NSString.stringWithContentsOfFileEncodingError(
        $(p), $.NSUTF8StringEncoding, null
    );
    return ns;
}

var htmlContent  = readUTF8(htmlPath);
var plainContent = readUTF8(plainPath);

var pb = $.NSPasteboard.generalPasteboard;
pb.clearContents();
pb.setStringForType(htmlContent,  'public.html');
pb.setStringForType(plainContent, 'public.utf8-plain-text');
`;
    fs.writeFileSync(jxaFile, jxa, 'utf8');
    try {
        execSync(`osascript -l JavaScript "${jxaFile}"`, { stdio: 'pipe' });
    } finally {
        cleanup([jxaFile]);
    }
}

// ── Windows: PowerShell + CF_HTML ───────────
function winSetClipboard(htmlFile, plainFile, id, tmp, tableHtml, plain) {
    const cfHtml  = buildCFHtml(tableHtml);
    const cfFile  = path.join(tmp, `excel_copy_${id}_cf.txt`);
    const psFile  = path.join(tmp, `excel_copy_${id}.ps1`);

    // CF_HTML 포맷 (Windows 클립보드 HTML 표준)
    fs.writeFileSync(cfFile, cfHtml, 'utf8');

    const escapedCF   = cfFile.replace(/\\/g, '\\\\');
    const escapedPlain = plainFile.replace(/\\/g, '\\\\');

    const ps = `
Add-Type -AssemblyName System.Windows.Forms
$cfHtml   = [System.IO.File]::ReadAllText('${escapedCF}',    [System.Text.Encoding]::UTF8)
$txtData  = [System.IO.File]::ReadAllText('${escapedPlain}', [System.Text.Encoding]::UTF8)
$data = New-Object System.Windows.Forms.DataObject
$data.SetData('HTML Format', $cfHtml)
$data.SetData([System.Windows.Forms.DataFormats]::UnicodeText, $txtData)
[System.Windows.Forms.Clipboard]::SetDataObject($data, $true)
`;
    fs.writeFileSync(psFile, ps, 'utf8');
    try {
        execSync(`powershell -NoProfile -ExecutionPolicy Bypass -File "${psFile}"`, { stdio: 'pipe' });
    } finally {
        cleanup([cfFile, psFile]);
    }
}

// ── Linux: xclip ────────────────────────────
function linuxSetClipboard(htmlFile) {
    // xclip 없으면 에러 → 위에서 catch 해서 안내 메시지 표시
    execSync(`xclip -selection clipboard -t text/html < "${htmlFile}"`, { stdio: 'pipe' });
}

// ──────────────────────────────────────────────
// 4. Windows CF_HTML 포맷 빌더
//    https://docs.microsoft.com/en-us/windows/win32/dataxchg/html-clipboard-format
// ──────────────────────────────────────────────
function buildCFHtml(tableHtml) {
    // 헤더 자리수 고정 (10자리) → 오프셋 계산 후 치환
    const PLACEHOLDER = '0000000000'; // 10자리

    const headerTemplate =
        `Version:0.9\r\n` +
        `StartHTML:${PLACEHOLDER}\r\n` +
        `EndHTML:${PLACEHOLDER}\r\n` +
        `StartFragment:${PLACEHOLDER}\r\n` +
        `EndFragment:${PLACEHOLDER}\r\n`;

    const headerLen = Buffer.byteLength(headerTemplate, 'utf8');

    const pre  = '<!DOCTYPE html>\r\n<html>\r\n<body>\r\n<!--StartFragment-->';
    const post = '<!--EndFragment-->\r\n</body>\r\n</html>';

    const startHTML     = headerLen;
    const startFragment = headerLen + Buffer.byteLength(pre, 'utf8');
    const endFragment   = startFragment + Buffer.byteLength(tableHtml, 'utf8');
    const endHTML       = endFragment + Buffer.byteLength(post, 'utf8');

    const pad = n => String(n).padStart(10, '0');
    const header =
        `Version:0.9\r\n` +
        `StartHTML:${pad(startHTML)}\r\n` +
        `EndHTML:${pad(endHTML)}\r\n` +
        `StartFragment:${pad(startFragment)}\r\n` +
        `EndFragment:${pad(endFragment)}\r\n`;

    return header + pre + tableHtml + post;
}

// ──────────────────────────────────────────────
// 5. 유틸
// ──────────────────────────────────────────────
function cleanup(files) {
    files.forEach(f => { try { fs.unlinkSync(f); } catch {} });
}

module.exports = { activate, deactivate };
