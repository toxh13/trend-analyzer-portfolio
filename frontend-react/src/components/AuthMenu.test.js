import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import axios from 'axios';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import { clearCsrfToken, refreshCsrfToken } from '../api/csrf';
import AuthMenu from './AuthMenu';

jest.mock('axios');
jest.mock('../api/csrf', () => ({
    clearCsrfToken: jest.fn(),
    refreshCsrfToken: jest.fn(),
}));

function renderAuthMenu() {
    return render(
        <MemoryRouter initialEntries={['/categories/it-science']}>
            <Routes>
                <Route path="/categories/it-science" element={<AuthMenu />} />
                <Route path="/" element={<div>홈 화면</div>} />
            </Routes>
        </MemoryRouter>
    );
}

describe('AuthMenu logout', () => {
    let consoleErrorSpy;

    beforeEach(() => {
        jest.clearAllMocks();
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
        refreshCsrfToken.mockResolvedValue({
            token: 'fresh-csrf-token',
            headerName: 'X-XSRF-TOKEN',
        });
        axios.get.mockResolvedValue({
            data: {
                authenticated: true,
                username: 'tester',
                email: 'tester@example.com',
                provider: 'GOOGLE',
                role: 'ROLE_ADMIN',
                discordLinked: false,
            },
        });
    });

    afterEach(() => {
        consoleErrorSpy.mockRestore();
    });

    it('moves to the home page after the server invalidates the session', async () => {
        axios.post.mockResolvedValue({ data: { authenticated: false } });
        renderAuthMenu();

        fireEvent.click(await screen.findByRole('button', { name: /tester/ }));
        fireEvent.click(screen.getByRole('button', { name: '로그아웃' }));

        await waitFor(() => expect(axios.post).toHaveBeenCalledWith(
            expect.stringContaining('/api/v1/auth/logout'),
            null,
            {
                withCredentials: true,
                headers: { 'X-XSRF-TOKEN': 'fresh-csrf-token' },
            }
        ));
        expect(refreshCsrfToken).toHaveBeenCalledTimes(1);
        expect(clearCsrfToken).toHaveBeenCalledTimes(1);
        expect(await screen.findByText('홈 화면')).toBeInTheDocument();
    });

    it('shows a visible error when logout fails', async () => {
        axios.post.mockRejectedValue(new Error('logout failed'));
        renderAuthMenu();

        fireEvent.click(await screen.findByRole('button', { name: /tester/ }));
        fireEvent.click(screen.getByRole('button', { name: '로그아웃' }));

        expect(await screen.findByRole('alert')).toHaveTextContent(
            '로그아웃에 실패했습니다. 다시 시도해 주세요.'
        );
        expect(clearCsrfToken).not.toHaveBeenCalled();
    });
});
