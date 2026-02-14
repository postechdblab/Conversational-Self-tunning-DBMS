"use client";
import { Drawer, DrawerBody, DrawerContent, DrawerHeader, DrawerOverlay, SlideDirection } from "@chakra-ui/react";
import React from "react";

export default function SideBar({ title, isOpen, setIsOpen, children }: { title: string; isOpen: boolean, setIsOpen: React.Dispatch<React.SetStateAction<boolean>>, children: React.ReactNode }) {

    return (
        <React.Fragment>
            <Drawer
                placement={"left" as SlideDirection}
                onClose={() => setIsOpen(false)}
                isOpen={isOpen}
                size={"lg"}
            >
                <DrawerOverlay />
                <DrawerContent>
                    <DrawerHeader borderBottomWidth="1px">{title}</DrawerHeader>
                    <DrawerBody>{children}</DrawerBody>
                </DrawerContent>
            </Drawer>
        </React.Fragment>
    );
}
