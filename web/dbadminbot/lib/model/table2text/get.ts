'use client';
import { getSummarizationResult } from '@/lib/api/frontend/table2text';
import { summarizationInput, summarizationResult } from '@/lib/model/table2text/type';
import useSWR from 'swr';

export function useSummarizationFromTable(rowValues: summarizationInput) {
    // Define the key for SWR based on the dbName and query.
    // If either is not present, use null to avoid fetching.
    const swrKey = rowValues != null && rowValues != undefined ? ['getSummarizationResult', rowValues] : null;

    // Define the fetcher function directly using getQueryResult, avoiding the use of useSWRWrapper.
    const fetcher = swrKey ? () => getSummarizationResult(rowValues) : null;

    // Call useSWR at the top level, passing the key and fetcher.
    const { data, error } = useSWR<summarizationResult>(swrKey, fetcher);

    // isLoading is not directly provided by useSWR, so it must be derived from `data` and `error`.
    const isLoading = !data && !error;

    return {
        data,
        isLoading,
        isError: !!error, // Convert error to a boolean indicating if there is an error
    };
}