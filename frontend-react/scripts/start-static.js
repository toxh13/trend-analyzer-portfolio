// 개발용: 공용 고정 데이터(fixtures/site/data)를 public/data로 복사한 뒤 static 모드로 개발 서버를 띄웁니다.
//   npm run start:static
// 다른 정적 JSON을 보려면 STATIC_FIXTURE_DIR=<디렉터리> 로 지정합니다(예: analytics/build_site.py 출력).
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const projectRoot = path.resolve(__dirname, '..');
const sourceDir = path.resolve(
    projectRoot,
    process.env.STATIC_FIXTURE_DIR || path.join('..', 'fixtures', 'site', 'data')
);
const targetDir = path.join(projectRoot, 'public', 'data');

if (!fs.existsSync(path.join(sourceDir, 'meta.json'))) {
    console.error(`정적 JSON을 찾지 못했습니다: ${sourceDir}`);
    process.exit(1);
}

fs.rmSync(targetDir, { recursive: true, force: true });
fs.cpSync(sourceDir, targetDir, { recursive: true });
console.log(`정적 JSON 복사: ${sourceDir} -> ${targetDir}`);

const reactScripts = require.resolve('react-scripts/bin/react-scripts.js');
const child = spawn(process.execPath, [reactScripts, 'start'], {
    stdio: 'inherit',
    env: { ...process.env, REACT_APP_DATA_MODE: 'static' },
});
child.on('exit', (code) => process.exit(code ?? 0));
