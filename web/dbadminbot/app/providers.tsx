"use client";

import { ChakraProvider } from "@chakra-ui/react";
import { NextUIProvider } from "@nextui-org/react";

export function Providers({ children }: { children: React.ReactNode }) {
    return (
        <NextUIProvider>
            <ChakraProvider>
                {children}
            </ChakraProvider>
        </NextUIProvider>
    );
}
