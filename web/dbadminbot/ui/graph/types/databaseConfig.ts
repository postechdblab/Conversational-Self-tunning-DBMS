import { EdgeConfig } from "@/ui/graph/types/edgeConfig";
import { SchemaColors } from "@/ui/graph/types/schemaColors";
import { TableConfig } from "@/ui/graph/types/tableConfig";
import { TablePositions } from "@/ui/graph/types/tablePositions";

export type Database = {
  name: string;
  description: string;
};

export type Databases = {
  [databaseName: string] : Database
};

export type DatabaseConfig = {
  tables: TableConfig[],
  edgeConfigs: EdgeConfig[],
  schemaColors: SchemaColors,
  tablePositions: TablePositions
};

export type DatabaseConfigs = {
  [databaseName: string] : DatabaseConfig
};