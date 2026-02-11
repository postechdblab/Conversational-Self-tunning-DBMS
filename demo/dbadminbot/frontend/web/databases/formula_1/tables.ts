import { TableConfig } from "@/ui/graph/types/tableConfig";

import circuitsTable from "./tables/circuits.json";
import constructorresultsTable from "./tables/constructorresults.json";
import constructorsTable from "./tables/constructors.json";
import constructorstandingsTable from "./tables/constructorstandings.json";
import driversTable from "./tables/drivers.json";
import driverstandingsTable from "./tables/driverstandings.json";
import laptimesTable from "./tables/laptimes.json";
import pitstopsTable from "./tables/pitstops.json";
import qualifyingTable from "./tables/qualifying.json";
import racesTable from "./tables/races.json";
import resultsTable from "./tables/results.json";
import seasonsTable from "./tables/seasons.json";
import statusTable from "./tables/status.json";

const tables: TableConfig[] = [
  circuitsTable,
  constructorresultsTable,
  constructorsTable,
  constructorstandingsTable,
  driversTable,
  driverstandingsTable,
  laptimesTable,
  pitstopsTable,
  qualifyingTable,
  racesTable,
  resultsTable,
  seasonsTable,
  statusTable
];

export default tables;
