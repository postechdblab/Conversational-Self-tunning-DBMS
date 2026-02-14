import { MODEL_API_ADDR, responseHeaderJson, responseMethodPost, responseStatusValid } from "@/lib/api/utils";
import { queryResult } from "@/lib/query/type";


interface Params {
    rowValues: queryResult; 
}

async function getModelResult(rowValues: queryResult): Promise<string> {
    const addr = MODEL_API_ADDR + "/table_to_text";
    console.log("rowValues: ", rowValues);
    return await fetch(addr, {
        body: JSON.stringify({
            rows: rowValues,
        }),
        ...responseHeaderJson,
        ...responseMethodPost,
    }).then((res) => res.json());
}

export async function POST(request: Request) {
    const requestBody = (await request.json()) as Params;

    // Get keys from Params interface
    const paramKeys: (keyof Params)[] = ["rowValues"];
    const missingKeys = paramKeys.filter((key) => !(key in requestBody));
    if (missingKeys.length) {
        console.warn(`Invalid request body. Missing keys: ${JSON.stringify(missingKeys)}`);
        throw new Error(`Invalid request body. Missing keys: ${JSON.stringify(missingKeys)}`);
    }

    const data = await getModelResult(requestBody.rowValues);
    
    // const data = JSON.stringify({"summary":"The table has been converted to text."});
    return new Response(JSON.stringify(data), { ...responseHeaderJson, ...responseStatusValid });
}