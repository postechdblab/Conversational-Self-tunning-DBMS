export type queryResultItem = {
    [key: string]: string | number;
};

export type queryResult = queryResultItem[];

export type tunerQueryResult = {
    data: queryResult;
    execution_time: number;
    queries: string[];
    execution_times: number[];
};
