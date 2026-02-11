'use client';
// type Tail<T extends any[]> = ((...t: T) => void) extends (
//     _: any,
//     ...tail: infer TT
// ) => void
//     ? TT
//     : [];

// This wrapper removes the first element of the query key and passes the rest to the query function.
export const useSWRWrapper = <T extends unknown[], R>(
    queryFn: (...args: T) => R,
) => {
    const tmp = (queryKey: T): R => {
        const [_, ...rest] = queryKey;
        const restQueryKey = rest as T;
        return queryFn(...restQueryKey);
    };
    return tmp;
};