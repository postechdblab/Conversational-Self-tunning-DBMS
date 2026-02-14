import { TableColumnConfig } from "@/ui/graph/types/tableColumnConfig";

export interface TableConfig {
  schema?: string;
  schemaColor?: string;
  name: string;
  description?: string;
  columns: TableColumnConfig[];
}