import { MODEL_API_ADDR, responseHeaderJson, responseMethodPost, responseStatusValid } from "@/lib/api/utils";

async function getModelResult(dbName: string, question: string, resetHistory: boolean): Promise<string> {
    const addr = MODEL_API_ADDR + "/text_to_sql"
    console.log(`dbName: ${dbName} question: ${question}`);
    return await fetch(addr, {
        body: JSON.stringify({
            text: question,
            db_id: dbName,
            analyse: true,
            reset_history: resetHistory,
        }),
        ...responseHeaderJson,
        ...responseMethodPost,
    }).then((res) => res.json());
}

export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const dbName = searchParams.get("dbName") ?? "";
    const question = searchParams.get("question") ?? "";
    const resetHistory = searchParams.get("resetHistory") ?? "";

    // Check if arguments are valid
    if (dbName == "") {
        return new Response("dbName is empty")
    }
    else if(question == "") {
        return new Response("question is empty")
    }
    else if(resetHistory == "") {
        return new Response("resetHistory is empty")
    }
    console.log(`dbdbdbdbdb: ${dbName}, question: ${question}, resetHistory: ${resetHistory}`)

    // Handle query
    const data = await getModelResult(dbName, question, resetHistory=="true");
    return new Response(JSON.stringify(data), { ...responseHeaderJson, ...responseStatusValid });
}