import axios from 'axios';

import {
    clearCsrfToken,
    ensureCsrfToken,
    installCsrfInterceptor,
    refreshCsrfToken,
} from './csrf';

jest.mock('axios');

describe('CSRF token cache', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        clearCsrfToken();
    });

    it('loads a new token when refresh is requested', async () => {
        axios.get
            .mockResolvedValueOnce({
                data: { token: 'cached-token', headerName: 'X-XSRF-TOKEN' },
            })
            .mockResolvedValueOnce({
                data: { token: 'fresh-token', headerName: 'X-XSRF-TOKEN' },
            });

        expect(await ensureCsrfToken()).toEqual({
            token: 'cached-token',
            headerName: 'X-XSRF-TOKEN',
        });
        expect(await refreshCsrfToken()).toEqual({
            token: 'fresh-token',
            headerName: 'X-XSRF-TOKEN',
        });
        expect(axios.get).toHaveBeenCalledTimes(2);
    });

    it('refreshes the token before every mutating request', async () => {
        let requestInterceptor;
        axios.defaults = {};
        axios.interceptors = {
            request: {
                use: jest.fn((interceptor) => {
                    requestInterceptor = interceptor;
                }),
            },
        };
        axios.get
            .mockResolvedValueOnce({
                data: { token: 'first-token', headerName: 'X-XSRF-TOKEN' },
            })
            .mockResolvedValueOnce({
                data: { token: 'second-token', headerName: 'X-XSRF-TOKEN' },
            });

        installCsrfInterceptor();

        const firstRequest = await requestInterceptor({ method: 'post', headers: {} });
        const secondRequest = await requestInterceptor({ method: 'patch', headers: {} });

        expect(firstRequest.headers['X-XSRF-TOKEN']).toBe('first-token');
        expect(secondRequest.headers['X-XSRF-TOKEN']).toBe('second-token');
        expect(axios.get).toHaveBeenCalledTimes(2);
    });
});
