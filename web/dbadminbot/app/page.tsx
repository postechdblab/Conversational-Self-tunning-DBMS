import Card from "@/components/home/card";
import ComponentGrid from "@/components/home/component-grid";
import WebVitals from "@/components/home/web-vitals";
import { Github, Youtube } from "@/components/shared/icons";
import { DEMO_URL, DEMO_VIDEO_URL, DEPLOY_URL } from "@/lib/constants";
import Image from "next/image";

export default async function Home() {

  return (
    <div className="flex min-h-screen w-full flex-col items-center justify-center">
      <div className="z-10 w-full max-w-xl px-5 xl:px-0">
        <a
          href={DEMO_VIDEO_URL}
          target="_blank"
          rel="noreferrer"
          className="mx-auto mb-5 flex max-w-fit animate-fade-up items-center justify-center space-x-2 overflow-hidden rounded-full bg-blue-100 px-7 py-2 transition-colors hover:bg-blue-200"
        >
          <Youtube className="h-5 w-5 text-[#1d9bf0]" />
          <p className="text-sm font-semibold text-[#1d9bf0]">
            Introducing DBAdminBot
          </p>
        </a>
        <h1
          className="animate-fade-up bg-gradient-to-br from-black to-stone-500 bg-clip-text text-center font-display text-4xl font-bold tracking-[-0.02em] text-transparent opacity-0 drop-shadow-sm [text-wrap:balance] md:text-7xl md:leading-[5rem]"
          style={{ animationDelay: "0.15s", animationFillMode: "forwards" }}
        >
          DBAdminBot
        </h1>
        <p
          className="mt-6 animate-fade-up text-center text-gray-500 opacity-0 [text-wrap:balance] md:text-xl"
          style={{ animationDelay: "0.25s", animationFillMode: "forwards" }}
        >
          Natural language interface to your favorite database system
        </p>
        <div
          className="mx-auto mt-6 flex animate-fade-up items-center justify-center space-x-5 opacity-0"
          style={{ animationDelay: "0.3s", animationFillMode: "forwards" }}
        >
          <a
            className="group flex max-w-fit items-center justify-center space-x-2 rounded-full border border-black bg-black px-5 py-2 text-sm text-white transition-colors hover:bg-white hover:text-black"
            href={DEMO_URL}
          >
            <svg
              className="h-4 w-4 group-hover:text-black"
              viewBox="0 0 24 24"
              fill="currentColor"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M12 4L20 20H4L12 4Z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <p>Live Demo</p>
          </a>
          <a
            className="flex max-w-fit items-center justify-center space-x-2 rounded-full border border-gray-300 bg-white px-5 py-2 text-sm text-gray-600 shadow-md transition-colors hover:border-gray-800"
            href="https://github.com/hyukkyukang/SQLBot"
            target="_blank"
            rel="noopener noreferrer"
          >
            <Github />
            <p>
              <span className="hidden sm:inline-block">Open source on GitHub</span>
            </p>
          </a>
        </div>
      </div>
      <div className="my-10 grid w-full max-w-screen-xl animate-fade-up grid-cols-1 gap-5 px-5 md:grid-cols-3 xl:px-0">
        {features.map(({ title, description, demo, large, xlarge, xxlarge }) => (
          <Card
            key={title}
            title={title}
            description={description}
            demo={
                demo
            }
            large={large}
            xlarge={xlarge}
            xxlarge={xxlarge}
          />
        ))}
      </div>
    </div>
  );
}

const features = [
  {
    title: "Conversational Database Interface (querying & tuning)",
    description:
      "Interact with databases without knowing SQL",
    large: false,
    xlarge: true,
    xxlarge: false,
    demo: <Image
    src="/tuning.png"
    alt="Deploy with Vercel"
    width={800}
    height={30}
    unoptimized
  />
  },
  {
    title: "Workload Visualization",
    description:
      "Graphically visualize workload history",
      large: false,
      xlarge: false,
      xxlarge: false,
      demo: <Image
    src="/workload_history.png"
    alt="Deploy with Vercel"
    width={800}
    height={30}
    unoptimized
  />,
  },
  {
    title: "Knob Tuning Results Visualization",
    description:
      "Graphically visualize knob tuning results",
    large: true,
    xlarge: false,
    xxlarge: false,
    demo: <Image
    src="/tuning_result.png"
    alt="Deploy with Vercel"
    width={800}
    height={30}
    unoptimized
  />
  }
];