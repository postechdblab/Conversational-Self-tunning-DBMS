import { PrismaClient as PC_concert_singer } from '@internal/prisma-concert_singer/client';
import { PrismaClient as PC_dorm_1 } from '@internal/prisma-dorm_1/client';
import { PrismaClient as PC_formula_1 } from "@internal/prisma-formula_1/client";
import { PrismaClient as PC_test } from '@prisma/client';

(BigInt.prototype as any).toJSON = function () {
    return this.toString();
};

const prisma_test = new PC_test()
const prisma_concert_singer = new PC_concert_singer()
const prisma_dorm_1 = new PC_dorm_1()
const prisma_formula_1 = new PC_formula_1()

export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const dbName = searchParams.get("dbName") ?? "";
    const tableName = searchParams.get("tableName") ?? "";
    
    // Check if arguments are valid
    if (dbName == "") {
        return new Response("dbName is empty")
    }
    else if(tableName == "") {
        return new Response("tableName is empty")
    }

    // route prisma to the correct database
    var prisma = null
    if(dbName == "test_db") {
        prisma = prisma_test
    }
    else if (dbName == "concert_singer") {
        prisma = prisma_concert_singer
    }
    else if (dbName == "dorm_1") {
        prisma = prisma_dorm_1
    }
    else if (dbName == "formula_1"){
        prisma = prisma_formula_1
    }
    else {
        // Raise error
        return new Response("Invalid DB name")
    }

    // Read in cars
    const getAllTableNamesQuery = "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';"
    const allTableNames = await prisma.$queryRawUnsafe(getAllTableNamesQuery) as { table_name: string }[];
    
    // Parse out table names
    const tableNames: string[] = allTableNames.map((element) => element["table_name"]);

    // Return array of error types for the model
    return new Response(JSON.stringify(tableNames));
}
