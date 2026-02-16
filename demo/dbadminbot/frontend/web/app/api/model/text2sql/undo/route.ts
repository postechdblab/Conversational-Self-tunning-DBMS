import { MODEL_API_ADDR, responseHeaderJson, responseMethodGet, responseStatusValid } from "@/lib/api/utils";

async function getUndoResponse(): Promise<string> {
    const addr = MODEL_API_ADDR + "/undo_last";
    return await fetch(addr, {
        ...responseHeaderJson,
        ...responseMethodGet,
    }).then((res) => res.json());
}

export async function GET(request: Request) {
    const data = await getUndoResponse();
    return new Response(JSON.stringify(data), { ...responseHeaderJson, ...responseStatusValid });
}
