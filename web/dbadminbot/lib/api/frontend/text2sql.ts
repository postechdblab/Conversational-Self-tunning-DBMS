import { API_ADDR, fetchWithTimeout } from '@/lib/api/utils';
import { translationResult } from '@/lib/model/text2sql/type';

export async function getTranslationResult(dbName: string, question: string, resetHistory: boolean): Promise<translationResult> {
    const addr = "/api/model/text2sql?dbName=" + dbName + "&resetHistory=" + resetHistory + "&question=" + question;
    // console.log(`addr: ${addr}`);
    return fetchWithTimeout(addr).then(res => res.json());
}
