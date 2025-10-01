-- CreateTable
CREATE TABLE "cars" (
    "id" INTEGER NOT NULL,
    "model" VARCHAR(255),
    "horsepower" INTEGER,
    "max_speed" INTEGER,
    "year" INTEGER,
    "price" DOUBLE PRECISION,

    CONSTRAINT "cars_pkey" PRIMARY KEY ("id")
);

