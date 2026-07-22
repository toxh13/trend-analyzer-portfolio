export function getErrorMessage(error, fallbackMessage) {
    return error?.response?.data?.message
        || error?.response?.data?.error
        || fallbackMessage;
}
