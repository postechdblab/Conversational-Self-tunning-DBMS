This is a [Next.js](https://nextjs.org/) project bootstrapped with [`create-next-app`](https://github.com/vercel/next.js/tree/canary/packages/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/basic-features/font-optimization) to automatically optimize and load Inter, a custom Google Font.

## Setup Database
### PostgreSQL Connection
Edit .env file to setup database address for prisma. 
```bash
DATABASE_URL="postgresql://{username}:{user_password}@{ip}:{port}/{db_name}?schema=public"
```

### Pull database schema
```bash
npx prisma db pull
npx prisma db pull --schema=./prisma-concert_singer/schema.prisma
npx prisma db pull --schema=./prisma-dorm_1/schema.prisma
npx prisma db pull --schema=./prisma-formula_1/schema.prisma
```

For details, please refer to the instruction in [prisma.io](https://www.prisma.io/docs/getting-started/setup-prisma/add-to-existing-project/relational-databases/connect-your-database-typescript-postgresql)

For using more than one database, please refer to [blog](https://www.kenaqshal.com/blog/connecting-to-multiple-databases-with-node-js-and-prisma#step-3:-defining-the-second-database-connection).

### Schema Visualization
First go to target DB in PostgreSQL, and run the following command to export schema to csv file.
```postgresql
\copy (SELECT
  t.table_schema,
  t.table_name,
  c.column_name,
  c.data_type,
  c.ordinal_position
FROM information_schema.tables t
LEFT JOIN information_schema.columns c
  ON t.table_schema = c.table_schema
    AND t.table_name = c.table_name
WHERE
  t.table_schema NOT IN ('information_schema', 'pg_catalog')
  AND t.table_name NOT IN ('schema_migrations', 'ar_internal_metadata')
ORDER BY 1, 2, 5) TO 'output.csv' DELIMITER ',' CSV HEADER;
```

Rename the output csv file
```bash
mv output.csv ${db_name}.csv
```

Then, clone [sql_schema_visualizer repository](https://github.com/sqlhabit/sql_schema_visualizer#how-to-visualize-your-schemas) and run below command to create json files for visualization.

```bash
npm run import ${db_name}
```
Then, the json config files will be saved under sql_schema_visualizer/src/config/databases/${db_name}.

Lastly, add the database name in web/ui/graph/config/databases.json.


### Generating Prisma Client components
We need to generate the prisma client components to import them in our react code.
```bash
npx prisma generate
npx prisma generate --schema=./prisma-concert_singer/schema.prisma
npx prisma generate --schema=./prisma-dorm_1/schema.prisma
npx prisma generate --schema=./prisma-formula_1/schema.prisma
```

For details, please refer to [sql_schema_visualizer](https://github.com/sqlhabit/sql_schema_visualizer#how-to-visualize-your-schemas)