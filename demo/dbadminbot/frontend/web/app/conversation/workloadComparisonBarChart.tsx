import { QuestionSqlPair, TuningResultPair } from '@/lib/model/tuning/type';
import { Table, TableBody, TableCell, TableColumn, TableHeader, TableRow } from "@nextui-org/react";
import { BarChart, Card, Subtitle, Title, TabGroup, TabList, Tab, TabPanels, TabPanel, Flex, Metric, Text, BadgeDelta } from "@tremor/react";
import React, { useMemo, useState } from "react";

function computeSpeedup(before: number, after: number): number | null {
  if (after > 0) return before / after;
  if (before > 0) return null; // Infinity: after=0 but before>0
  return 1; // both zero → no change
}

function formatSpeedup(speedup: number | null): string {
  if (speedup === null) return "∞";
  return `${speedup.toFixed(2)}x`;
}

export default function WorkloadComparisonBarChartWindow({
  title,
  questionSqlPairs,
  tuningResultPairs
}: {
  title: string,
  questionSqlPairs: QuestionSqlPair[],
  tuningResultPairs: TuningResultPair[] | null
}) {
  const [tabIndex, setTabIndex] = useState(0);

  const isValidData = useMemo(() =>
    questionSqlPairs?.length > 0 && tuningResultPairs && tuningResultPairs.length > 0,
    [questionSqlPairs, tuningResultPairs]
  );

  // Shared per-query computation used by both chart and table
  const perQueryData = useMemo(() => {
    if (!isValidData) return [];
    return questionSqlPairs.map((pair, index) => {
      const before = pair.execution_time;
      const after = tuningResultPairs?.[index]?.execution_time_after_tuning ?? before;
      return {
        qid: pair.qid,
        before,
        after,
        reduction: before - after,
        speedup: computeSpeedup(before, after),
      };
    });
  }, [questionSqlPairs, tuningResultPairs, isValidData]);

  // Bar chart data: reduction per query (ms saved)
  const reductionChartData = useMemo(() => {
    return perQueryData.map((row) => ({
      name: `qid: ${row.qid}`,
      "Reduction (ms)": parseFloat(row.reduction.toFixed(2)),
    }));
  }, [perQueryData]);

  const metrics = useMemo(() => {
    if (!isValidData || !tuningResultPairs) return { totalImprovement: 0, avgSpeedup: 0, avgReduction: 0 };
    let totalImprovement = 0;
    let totalSpeedup = 0;
    let finiteCount = 0;
    const n = perQueryData.length;
    for (const row of perQueryData) {
      totalImprovement += row.reduction;
      if (row.speedup !== null) {
        totalSpeedup += row.speedup;
        finiteCount++;
      }
    }
    return {
      totalImprovement,
      avgSpeedup: finiteCount > 0 ? totalSpeedup / finiteCount : 0,
      avgReduction: n > 0 ? totalImprovement / n : 0,
    };
  }, [perQueryData, tuningResultPairs, isValidData]);

  return (
    <Card>
      <Title>{title}</Title>
      {isValidData ? (
        <React.Fragment>
          <Flex className="mt-4 gap-4" justifyContent="start" flexDirection="row">
            <div className="text-center">
              <Text>Total Improvement</Text>
              <Metric className="text-lg">{metrics.totalImprovement.toFixed(2)} ms</Metric>
            </div>
            <div className="text-center">
              <Text>Avg Speedup</Text>
              <Metric className="text-lg">{metrics.avgSpeedup.toFixed(2)}x</Metric>
            </div>
            <div className="text-center">
              <Text>Avg Reduction</Text>
              <Flex justifyContent="center" className="gap-1">
                <Metric className="text-lg">{metrics.avgReduction.toFixed(2)} ms</Metric>
                <BadgeDelta
                  deltaType={metrics.avgReduction > 0 ? "moderateIncrease" : metrics.avgReduction < 0 ? "moderateDecrease" : "unchanged"}
                  size="xs"
                />
              </Flex>
            </div>
          </Flex>

          <TabGroup index={tabIndex} onIndexChange={setTabIndex} className="mt-4">
            <TabList variant="solid">
              <Tab>Time Reduction</Tab>
              <Tab>Absolute Times</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                <Subtitle className="mt-2">Execution time reduction per query (before - after)</Subtitle>
                <BarChart
                  data={reductionChartData}
                  index="name"
                  categories={["Reduction (ms)"]}
                  colors={["emerald"]}
                  valueFormatter={(value) => `${value} ms`}
                />
              </TabPanel>
              <TabPanel>
                <Table aria-label="Execution time comparison" className="mt-2">
                  <TableHeader>
                    <TableColumn>Query</TableColumn>
                    <TableColumn>Before (ms)</TableColumn>
                    <TableColumn>After (ms)</TableColumn>
                    <TableColumn>Reduction (ms)</TableColumn>
                    <TableColumn>Speedup</TableColumn>
                  </TableHeader>
                  <TableBody>
                    {perQueryData.map((row) => (
                      <TableRow key={row.qid}>
                        <TableCell>qid: {row.qid}</TableCell>
                        <TableCell>{row.before.toFixed(2)}</TableCell>
                        <TableCell>{row.after.toFixed(2)}</TableCell>
                        <TableCell>{row.reduction.toFixed(2)}</TableCell>
                        <TableCell>{formatSpeedup(row.speedup)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TabPanel>
            </TabPanels>
          </TabGroup>
        </React.Fragment>
      ) : (
        <p>No comparison data available</p>
      )}
    </Card>
  );
}
