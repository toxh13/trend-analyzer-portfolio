import axios from 'axios';
import { buildApiUrl } from '../utils/apiBaseUrl';

let cachedCsrfToken = null;
let csrfTokenPromise = null;
let interceptorInstalled = false;

async function loadCsrfToken() {
    const response = await axios.get(buildApiUrl('/api/v1/auth/csrf'), {
        withCredentials: true,
    });

    const token = response.data?.token;
    const headerName = response.data?.headerName || 'X-XSRF-TOKEN';

    if (!token) {
        return null;
    }

    cachedCsrfToken = { token, headerName };
    return cachedCsrfToken;
}

export async function ensureCsrfToken() {
    if (cachedCsrfToken) {
        return cachedCsrfToken;
    }

    if (!csrfTokenPromise) {
        csrfTokenPromise = loadCsrfToken().finally(() => {
            csrfTokenPromise = null;
        });
    }

    return csrfTokenPromise;
}

export async function refreshCsrfToken() {
    cachedCsrfToken = null;
    return loadCsrfToken();
}

export function clearCsrfToken() {
    cachedCsrfToken = null;
}

export function installCsrfInterceptor() {
    if (interceptorInstalled) {
        return;
    }

    interceptorInstalled = true;
    axios.defaults.withCredentials = true;

    axios.interceptors.request.use(async (config) => {
        const method = String(config.method || 'get').toLowerCase();
        const isMutatingRequest = ['post', 'put', 'patch', 'delete'].includes(method);

        if (!isMutatingRequest) {
            return config;
        }

        const headers = config.headers || {};
        if (headers['X-XSRF-TOKEN'] || headers['x-xsrf-token']) {
            return config;
        }

        const csrfToken = await refreshCsrfToken();
        if (csrfToken?.token) {
            headers[csrfToken.headerName] = csrfToken.token;
            config.headers = headers;
        }

        return config;
    });
}
