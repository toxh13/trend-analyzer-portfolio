// 화면이 데이터를 어디서 읽을지 정하는 빌드 설정입니다.
// - 기본(api): v1처럼 Spring API를 호출합니다.
// - static: GitHub Pages에 함께 배포된 정적 JSON(v2)을 읽습니다. 서버가 없으므로 로그인·관리자 기능을 숨깁니다.
// 빌드 시점에는 CRA가 process.env 값을 상수로 바꾸고, 테스트에서는 호출할 때마다 현재 값을 읽습니다.
export function isStaticMode() {
    return process.env.REACT_APP_DATA_MODE === 'static';
}

// 정적 JSON 위치입니다. 기본값은 배포 경로 아래 data/ 입니다(예: /trend-analyzer-portfolio/data).
export function getStaticDataBase() {
    const configured = (process.env.REACT_APP_STATIC_DATA_BASE || '').trim();
    const base = configured || `${process.env.PUBLIC_URL || ''}/data`;
    return base.replace(/\/+$/, '');
}
