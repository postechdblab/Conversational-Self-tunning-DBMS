import { QuestionSqlPair, TuningResultPair } from '@/lib/model/tuning/type';
import { BarChart, Card, Subtitle, Title } from "@tremor/react";
import React, { useMemo } from "react";

export default function WorkloadComparisonBarChartWindow({
  title,
  questionSqlPairs,
  tuningResultPairs
}: {
  title: string,
  questionSqlPairs: QuestionSqlPair[],
  tuningResultPairs: TuningResultPair[] | null
}) {
  const isValidData = useMemo(() =>
    questionSqlPairs?.length > 0 && tuningResultPairs && tuningResultPairs.length > 0,
    [questionSqlPairs, tuningResultPairs]
  );

  const data = useMemo(() => {
    if (!isValidData) return [];
    return questionSqlPairs.map((pair, index) => ({
      name: `qid: ${pair.qid}`,
      before: pair.execution_time,
      after: tuningResultPairs?.[index]?.execution_time_after_tuning ?? 0
    }));
  }, [questionSqlPairs, tuningResultPairs, isValidData]);

  let improvement = 0;
  if (tuningResultPairs) {
    for (let i = 0; i < tuningResultPairs.length; ++i) {
      improvement += tuningResultPairs[i].execution_time - tuningResultPairs[i].execution_time_after_tuning;
    }
  }
  return (
    <Card>
      <Title>{title}</Title>
      {isValidData ? (
        <React.Fragment>
          <Subtitle>{improvement.toFixed(2)}ms improvement in total</Subtitle>
          <BarChart
            data={data}
            index="name"
            categories={['before', 'after']}
            colors={['red', 'green']}
            valueFormatter={(value) => `${value} ms`}
          />
        </React.Fragment>
      ) : (
        <p>No comparison data available</p>
      )}
    </Card>
  );
}
