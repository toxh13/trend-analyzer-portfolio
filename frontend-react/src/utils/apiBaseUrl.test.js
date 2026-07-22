import { buildApiUrl, getApiRoot } from './apiBaseUrl';

describe('apiBaseUrl', () => {
    const originalApiUrl = process.env.REACT_APP_API_URL;

    afterEach(() => {
        process.env.REACT_APP_API_URL = originalApiUrl;
        jest.restoreAllMocks();
    });

    it('falls back to a relative path for empty or malformed values', () => {
        const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});

        process.env.REACT_APP_API_URL = '';
        expect(getApiRoot()).toBe('');

        process.env.REACT_APP_API_URL = 'http:/broken-host';
        expect(getApiRoot()).toBe('');

        expect(warnSpy).toHaveBeenCalled();
    });

    it('normalizes a valid absolute base URL and joins paths safely', () => {
        process.env.REACT_APP_API_URL = 'https://example.com/';

        expect(getApiRoot()).toBe('https://example.com');
        expect(buildApiUrl('api/v1/trends')).toBe('https://example.com/api/v1/trends');
        expect(buildApiUrl('/api/v1/trends')).toBe('https://example.com/api/v1/trends');
    });
});
