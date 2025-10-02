import { TableConfig } from "@/ui/graph/types/tableConfig";

import dormTable from "./tables/dorm.json";
import dormAmenityTable from "./tables/dorm_amenity.json";
import hasAmenityTable from "./tables/has_amenity.json";
import livesInTable from "./tables/lives_in.json";
import studentTable from "./tables/student.json";

const tables: TableConfig[] = [
  dormTable,
  dormAmenityTable,
  hasAmenityTable,
  livesInTable,
  studentTable
];

export default tables;
