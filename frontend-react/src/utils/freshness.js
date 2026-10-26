// v2 배포본 meta.json의 freshness 값을 화면 문구로 바꿉니다.
// ok: 6시간 이내 성공 수집, stale: 6~24시간, down: 24시간 초과 또는 성공 기록 없음 (contracts/site/meta.schema.json)
export const FRESHNESS_PRESENTATION = {
    ok: { label: '정상', className: 'bg-emerald-50 text-emerald-700 border-emerald-100' },
    stale: { label: '지연', className: 'bg-amber-50 text-amber-800 border-amber-200' },
    down: { label: '중단', className: 'bg-rose-50 text-rose-700 border-rose-200' },
};

export function describeFreshness(meta) {
    const freshness = meta?.freshness;
    const hours = meta?.freshnessHours;
    if (freshness === 'down') {
        return hours == null
            ? '아직 성공한 수집 기록이 없습니다. 화면의 수치는 비어 있거나 예전 값일 수 있습니다.'
            : `마지막 성공 수집 후 ${hours}시간이 지났습니다. 수집이 멈춘 상태라 화면의 수치가 오래된 값입니다.`;
    }
    if (freshness === 'stale') {
        return `마지막 성공 수집 후 ${hours}시간이 지났습니다. 최근 몇 차례 수집이 늦어지거나 실패했습니다.`;
    }
    return '최근 6시간 안에 수집이 성공했습니다.';
}

// 서울 로컬 시각 문자열(예: 2026-10-24T12:00:00)을 화면용으로 바꿉니다.
export function formatSeoulLocal(value) {
    if (!value) return '-';
    return String(value).replace('T', ' ').slice(0, 16);
}
