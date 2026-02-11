import { queryResult } from "@/lib/query/type";

export type summarizationInput = {
    rows: queryResult;
}

export type summarizationResult = {
    summary: string;
}
