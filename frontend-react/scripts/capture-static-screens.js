// static 빌드를 GitHub Pages와 같은 하위 경로(/trend-analyzer-portfolio/)로 띄워 주요 화면을 캡처합니다.
// 사전 준비: REACT_APP_DATA_MODE=static PUBLIC_URL=/trend-analyzer-portfolio npm run build
// 실행:     node scripts/capture-static-screens.js [출력 디렉터리]   (기본 ../docs/v2/screens)
// Playwright는 프로젝트 의존성에 넣지 않았습니다. 설치된 Playwright·Chromium을 쓰고,
// 브라우저 경로는 PLAYWRIGHT_CHROMIUM_PATH(기본 /opt/pw-browsers/chromium)로 바꿀 수 있습니다.
const fs = require('fs');
const http = require('http');
const path = require('path');
const { chromium } = require('playwright');

const BASE_PATH = '/trend-analyzer-portfolio';
const projectRoot = path.resolve(__dirname, '..');
const buildDir = path.join(projectRoot, 'build');
const dataDir = path.resolve(projectRoot, process.env.STATIC_FIXTURE_DIR || '../fixtures/site/data');
const outDir = path.resolve(projectRoot, process.argv[2] || '../docs/v2/screens');
const CONTENT_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript',
    '.css': 'text/css',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.ico': 'image/x-icon',
};

// 화면별로 meta.json을 바꿔 신선도 안내를 확인할 수 있게 합니다.
let metaOverride = null;

// GitHub Pages처럼 하위 경로만 서빙하고, 없는 파일은 404를 돌려주는 최소 정적 서버입니다.
function startServer() {
    const server = http.createServer((req, res) => {
        const url = decodeURIComponent(req.url.split('?')[0]);
        if (!url.startsWith(`${BASE_PATH}/`)) {
            res.writeHead(404).end('not found');
            return;
        }
        let relative = url.slice(BASE_PATH.length + 1) || 'index.html';
        let file = relative.startsWith('data/')
            ? path.join(dataDir, relative.slice('data/'.length))
            : path.join(buildDir, relative);
        if (relative === 'data/meta.json' && metaOverride) {
            const meta = { ...JSON.parse(fs.readFileSync(file, 'utf8')), ...metaOverride };
            res.writeHead(200, { 'Content-Type': CONTENT_TYPES['.json'] }).end(JSON.stringify(meta));
            return;
        }
        if (!fs.existsSync(file) || fs.statSync(file).isDirectory()) {
            res.writeHead(404).end('not found');
            return;
        }
        res.writeHead(200, { 'Content-Type': CONTENT_TYPES[path.extname(file)] || 'application/octet-stream' });
        fs.createReadStream(file).pipe(res);
    });
    return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)));
}

async function main() {
    fs.mkdirSync(outDir, { recursive: true });
    const server = await startServer();
    const origin = `http://127.0.0.1:${server.address().port}${BASE_PATH}/`;
    const browser = await chromium.launch({
        executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH || '/opt/pw-browsers/chromium',
    });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    // 외부 폰트 요청은 막아 캡처가 네트워크에 묶이지 않게 합니다.
    await page.route('https://fonts.googleapis.com/**', (route) => route.abort());
    const pageErrors = [];
    page.on('pageerror', (error) => pageErrors.push(error.message));

    const shot = async (name) => {
        // recharts 애니메이션(기본 1.5초)이 끝난 뒤 찍습니다.
        await page.waitForTimeout(2000);
        await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true });
        console.log(`saved ${name}.png`);
    };

    // 1. 인기 키워드(홈)
    await page.goto(origin);
    await page.getByText('인공지능').first().waitFor();
    await shot('01-home');

    // 2. 키워드 상세: 직접 링크 + 새로고침
    await page.goto(`${origin}#/keywords/${encodeURIComponent('인공지능')}`);
    await page.reload();
    await page.getByText('고정 기사 14').first().waitFor();
    await shot('02-keyword-detail');

    // 3. 카테고리 분석: 직접 링크
    await page.goto(`${origin}#/categories/economy`);
    await page.getByText('환율').first().waitFor();
    await shot('03-category');

    // 4. 키워드 비교 + 근거 기사: 공유 링크로 열고 날짜 선택
    const compareQuery = new URLSearchParams({ first: 'AI', second: '반도체', days: '7' });
    await page.goto(`${origin}#/history?${compareQuery}`);
    await page.reload();
    await page.getByRole('button', { name: /인공지능 2026-10-23/ }).first().dispatchEvent('click');
    await page.getByText('고정 기사 13').first().waitFor();
    await shot('04-history-compare');

    // 5. 같은 대표 키워드 비교 거부(v1 오류 문구)
    const sameQuery = new URLSearchParams({ first: '인공지능', second: 'A.I.', days: '7' });
    await page.goto(`${origin}#/history?${sameQuery}`);
    await page.reload();
    await page.getByText('같은 대표 키워드로 해석되어').first().waitFor();
    await shot('05-history-same-canonical');

    // 6. 운영 현황
    await page.goto(`${origin}#/status`);
    await page.reload();
    await page.getByRole('table').waitFor();
    await shot('06-status');

    // 7. 수집 지연 안내(stale)
    metaOverride = { freshness: 'stale', freshnessHours: 9.5 };
    await page.goto(`${origin}#/`);
    await page.reload();
    await page.getByText('데이터 수집이 지연되고 있습니다.').waitFor();
    await shot('07-freshness-stale');
    metaOverride = null;

    // 8. 모바일 폭
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${origin}#/`);
    await page.reload();
    await page.getByText('인공지능').first().waitFor();
    await shot('08-home-mobile');

    await browser.close();
    server.close();
    if (pageErrors.length) {
        console.error('페이지 오류:', pageErrors);
        process.exit(1);
    }
}

main().catch((error) => {
    console.error(error);
    process.exit(1);
});
