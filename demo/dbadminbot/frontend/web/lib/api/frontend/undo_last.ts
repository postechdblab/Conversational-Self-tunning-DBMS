import { fetchWithTimeout } from '@/lib/api/utils';

export async function getUndoLastResponse(): Promise<{ response: boolean }> {
    const addr = "/api/model/text2sql/undo";
    return fetchWithTimeout(addr).then(res => res.json());
}
