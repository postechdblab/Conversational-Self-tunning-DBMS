import { TableConfig } from "@/ui/graph/types/tableConfig";

import concertTable from "./tables/concert.json";
import singerTable from "./tables/singer.json";
import singerInConcertTable from "./tables/singer_in_concert.json";
import stadiumTable from "./tables/stadium.json";

const tables: TableConfig[] = [
  concertTable,
  singerTable,
  singerInConcertTable,
  stadiumTable
];

export default tables;
