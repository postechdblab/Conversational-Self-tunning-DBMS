"use client";
import { Listbox, ListboxItem } from "@nextui-org/react";
import React from "react";

export const ListboxWrapper = ({ children }: { children: React.ReactNode }) => (
    <div className="w-[260px] border-small px-1 py-2 rounded-small border-default-200 dark:border-default-100">{children}</div>
);

export default function ListBox({
    itemList: itemList,
    selectedItem: selectedItem,
    setSelectedItem: setSelectedItem,
}: {
    itemList: string[];
    selectedItem: string;
    setSelectedItem: React.Dispatch<React.SetStateAction<string>>;
}) {

    return (
        <div className="flex flex-col gap-2">
            <ListboxWrapper>
                <Listbox
                    aria-label="Single selection example"
                    variant="flat"
                    disallowEmptySelection
                    selectionMode="single"
                    onAction={(value) => {setSelectedItem(value as string)}}
                >
                    {itemList.map((item) => (
                        <ListboxItem key={item} value={item}>
                            {item}
                        </ListboxItem>
                    ))}
                </Listbox>
            </ListboxWrapper>
            <p className="text-small text-default-500">Selected item: {selectedItem}</p>
        </div>
    );
}
