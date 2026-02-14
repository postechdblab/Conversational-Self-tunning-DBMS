import { MODEL_API_ADDR, responseHeaderJson, responseMethodGet, responseStatusValid } from "@/lib/api/utils";

async function getResetResponse(): Promise<string> {
    const addr = MODEL_API_ADDR + "/reset_history"
    return await fetch(addr, {
        ...responseHeaderJson,
        ...responseMethodGet,
    }).then((res) => res.json());
}

export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    // Handle query
    const data = await getResetResponse();
    return new Response(JSON.stringify(data), { ...responseHeaderJson, ...responseStatusValid });
}
