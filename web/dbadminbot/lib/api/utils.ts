export const API_ADDR = process.env.NEXT_PUBLIC_API_ADDR ?? "";
export const MODEL_API_ADDR = process.env.MODEL_API_ADDR ?? "";

export const responseHeaderJson = {
    headers: {
        "content-type": "application/json",
    },
};
export const responseStatusValid = {
    status: 200,
};

export const responseMethodPost = {
    method: "POST",
};

export const responseMethodGet = {
    method: "GET",
};

export interface RequestInitWithTimeout extends RequestInit {
    timeout?: number;
    body?: string;
    headers?: Record<string, string>;
    method?: string;
}

export async function fetchWithTimeout(resource: RequestInfo | URL, options: RequestInitWithTimeout = {}): Promise<Response> {
    const { timeout = 180000 } = options;

    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);

    const response = await fetch(resource, {
        ...options,
        signal: controller.signal,
    });
    clearTimeout(id);

    return response;
}
