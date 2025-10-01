import { Table, TableBody, TableCell, TableColumn, TableHeader, TableRow } from "@nextui-org/react";
import { Card, Subtitle, Title } from "@tremor/react";
import React from "react";

export default function ResultTable({ title, colNames, rows }: { title: string; colNames: string[]; rows: (string|number)[][] }) {
    return (
        <React.Fragment>
            <Card>
            <Title>{title}</Title>
            <Subtitle>
            {`Query result table with ${colNames.length} columns and ${rows.length} rows`}
            
            </Subtitle>
            <Table aria-label={title} className="pt-3">
                <TableHeader>
                {colNames.map((colName) => (
                    <TableColumn key={colName}>{colName}</TableColumn>
                ))}
                </TableHeader>
                <TableBody>
                    {
                        rows.map((row) => (
                            <TableRow key={row[0]}>
                                {row.map((col) => (
                                    <TableCell key={col}>{col}</TableCell>
                                ))}
                            </TableRow>
                        ))
                    }
                </TableBody>
            </Table>
            </Card>
        </React.Fragment>
    );
}
