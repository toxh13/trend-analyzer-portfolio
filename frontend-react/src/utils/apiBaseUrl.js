// 운영 환경에서는 Nginx가 /api, /oauth2, /login 경로를 백엔드로 프록시합니다.
// 따라서 REACT_APP_API_URL이 비어 있거나 잘못된 값이면 상대경로를 사용하는 것이 가장 안전합니다.
export function getApiRoot() {
    const rawValue = process.env.REACT_APP_API_URL;
    const value = rawValue ? rawValue.trim() : '';

    if (!value) {
        return '';
    }

    // GitHub Actions 또는 서버 env에서 실수로 "http:" / "http:/domain" 형태가 들어오면
    // Axios가 "Invalid URL: missing // after protocol" 에러를 발생시킵니다.
    // 이런 값은 운영 프록시 구조에 맞게 상대경로로 fallback합니다.
    if (value === 'http:' || value === 'https:' || (value.startsWith('http:/') && !value.startsWith('http://'))) {
        console.warn('Invalid REACT_APP_API_URL detected. Falling back to relative API path:', value);
        return '';
    }

    if (value.startsWith('https:/') && !value.startsWith('https://')) {
        console.warn('Invalid REACT_APP_API_URL detected. Falling back to relative API path:', value);
        return '';
    }

    if (value.startsWith('http://') || value.startsWith('https://')) {
        return value.replace(/\/$/, '');
    }

    // /api 같은 상대경로 base를 허용합니다.
    if (value.startsWith('/')) {
        return value.replace(/\/$/, '');
    }

    console.warn('Unsupported REACT_APP_API_URL detected. Falling back to relative API path:', value);
    return '';
}

export function buildApiUrl(path) {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${getApiRoot()}${normalizedPath}`;
}
