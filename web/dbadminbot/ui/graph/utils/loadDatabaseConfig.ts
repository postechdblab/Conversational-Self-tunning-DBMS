import { EdgeConfig } from "@/ui/graph/types/edgeConfig";
import { SchemaColors } from "@/ui/graph/types/schemaColors";
import { TableConfig } from "@/ui/graph/types/tableConfig";
import { TablePositions } from "@/ui/graph/types/tablePositions";
import { fullTableName } from "@/ui/graph/utils/fullTableName";

export const loadDatabaseConfig = async (databaseName: string) => {
  const edgeConfigs = (await import(`../../../databases/${databaseName}/edges.json`)).default as EdgeConfig[];
  const tablePositions = (await import(`../../../databases/${databaseName}/tablePositions.json`)).default as TablePositions;
  const schemaColors = (await import(`../../../databases/${databaseName}/schemaColors.json`)).default as SchemaColors;
  const tables = (await import(`../../../databases/${databaseName}/tables`)).default as TableConfig[];

  edgeConfigs.forEach((edgeConfig: EdgeConfig) => {
    const sourceTableName = fullTableName(edgeConfig.source);
    const targetTableName = fullTableName(edgeConfig.target);

    edgeConfig.source = sourceTableName;
    edgeConfig.target = targetTableName;
  });

  tables.forEach(table => {
    table.schemaColor = schemaColors[table.schema || "DEFAULT"];
  });

  return {
    tables,
    tablePositions,
    edgeConfigs,
    schemaColors
  };
}