import databases from "@/ui/graph/config/databases";
import { DatabaseConfigs } from "@/ui/graph/types/databaseConfig";
import { loadDatabaseConfig } from "@/ui/graph/utils/loadDatabaseConfig";

export const loadDatabases = async () => {
  const databaseConfigs: DatabaseConfigs = {};

  for (const databaseName of Object.keys(databases)) {
    const databaseConfig = await loadDatabaseConfig(databaseName);

    databaseConfigs[databaseName] = databaseConfig;
  }

  return databaseConfigs;
};