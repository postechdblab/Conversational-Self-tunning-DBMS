import { BuyMeACoffee } from "../shared/icons";

export default function Footer() {
  return (
    <div className="absolute w-full py-5 text-center">
      <p className="text-gray-500">
        {" "}
        <a
          className="font-semibold text-gray-600 underline-offset-4 transition-colors hover:underline"
          href="https://dslab.postech.ac.kr"
          target="_blank"
          rel="noopener noreferrer"
        >
          © 2023 Data Systems Lab @ POSTECH
        </a>
      </p>
    </div>
  );
}
