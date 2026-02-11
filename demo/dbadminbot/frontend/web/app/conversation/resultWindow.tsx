"use client";
import BarChartWindow from "@/app/conversation/barChart";
import WorkloadBarChartWindow from "@/app/conversation/workloadBarChart";
import WorkloadComparisonBarChartWindow from "@/app/conversation/workloadComparisonBarChart";
import { useQueryResultContext } from "@/context/queryResultContext";
import { useTuningResultContext } from "@/context/dbtuningContext";
import { queryResultToColNames, queryResultToRows, validateSameNumCols } from "@/lib/table/utils";
import ResultTable from "@/ui/table/table";
import { Card, CardBody, Tab, Tabs } from "@nextui-org/react";
import React, { useMemo } from "react";
import { useQuestionSqlContext } from "@/context/questionSqlContext";

export default function ResultWindow() {
  const { queryResult } = useQueryResultContext();
  const { questionSqlPairs } = useQuestionSqlContext();
  const { tuningResultPairs } = useTuningResultContext();
  const validResult = useMemo(() => validateSameNumCols(queryResult), [queryResult]);
  const colNames = useMemo(() => validResult && queryResult ? queryResultToColNames(queryResult) : [], [queryResult, validResult]);
  const rows = useMemo(() => validResult  && queryResult ? queryResultToRows(queryResult) : [[]], [queryResult, validResult]);
  const sqls_and_qids_in_order = useMemo(() => questionSqlPairs.map(pair => `${pair.qid} (${pair.sql})`), [questionSqlPairs]);
  const execution_times_in_order = useMemo(() => [questionSqlPairs.map(pair => pair.execution_time)], [questionSqlPairs]);
  const showResultTable = useMemo(() => validResult && queryResult && queryResult.length > 0, [validResult, queryResult]);
  const showComparisonBarChart = useMemo(() => tuningResultPairs.length > 0 && tuningResultPairs.length == questionSqlPairs.length, [tuningResultPairs, questionSqlPairs]);
  return (
        <React.Fragment>
          {showResultTable
          ?
            <div className="flex w-full flex-col">
              <Tabs aria-label="Options">
                <Tab key="Table" title="Table">
                <ResultTable title="Result Table" colNames={colNames} rows={rows} />
                </Tab>
                <Tab key="Bar Chart" title="Bar Chart">
                  <BarChartWindow title="Result Bar Chart" colNames={colNames} rows={rows} />
                </Tab>
                <Tab key="Workload" title="Execution Time">
                  <WorkloadBarChartWindow title="Execution Time Bar Chart" colNames={sqls_and_qids_in_order} rows={execution_times_in_order} />
                </Tab>
              </Tabs>
            </div>  
          :
          showComparisonBarChart
            ?
            <div className="flex w-full flex-col">
              <Tabs aria-label="Options">
                <Tab key="Tuning" title="Execution Time Comparison">
                  <WorkloadComparisonBarChartWindow title={"Execution Time Bar Chart"} questionSqlPairs={questionSqlPairs} tuningResultPairs={tuningResultPairs} />
                </Tab>
              </Tabs>
            </div>
            :
            <Card>
              <CardBody className="items-center">
                {validResult ? <p>Empty Result</p> : <p>Query result will be shown here</p>}
              </CardBody>
            </Card>
          }
        </React.Fragment>
    );
}
