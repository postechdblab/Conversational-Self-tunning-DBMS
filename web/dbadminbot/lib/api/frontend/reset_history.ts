import { fetchWithTimeout } from '@/lib/api/utils';

export async function getTranslationResetResponse(): Promise<boolean> {
    const addr = "/api/model/text2sql/reset";
    return fetchWithTimeout(addr).then(res => res.json());
}

