import { fetchWithTimeout } from '@/lib/api/utils';
import { tunerQueryResult } from '@/lib/query/type';

export async function getQueryResult(dbName: string, query: string): Promise<tunerQueryResult> {
    const addr = "http://localhost:1234/query";
    console.log('getQueryResult');
    return fetchWithTimeout(addr, {
        method: 'POST', headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(query),
    }).then(res => res.json());
}
