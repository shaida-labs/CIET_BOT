import type { SVGProps } from "react";

type CietLogoProps = SVGProps<SVGSVGElement> & {
  title?: string;
};

export function CietLogo({ title = "CIET Chalapathi", ...props }: CietLogoProps) {
  return (
    <svg viewBox="0 0 120 120" role="img" aria-label={title} {...props}>
      <title>{title}</title>
      <circle cx="60" cy="60" r="54" fill="#fffdf9" stroke="#e58a35" strokeWidth="2.4" />
      <circle cx="60" cy="35" r="10" fill="#f5f8fb" stroke="#255e90" strokeWidth="1.8" />
      <circle cx="60" cy="35" r="6" fill="#d7262f" />
      <path d="M53 35h14M60 28v14" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" />
      <text
        x="60"
        y="57"
        textAnchor="middle"
        fontFamily="Inter, Arial, sans-serif"
        fontSize="25"
        fontWeight="900"
        fill="#d7232a"
      >
        CIET
      </text>
      <text
        x="60"
        y="78"
        textAnchor="middle"
        fontFamily="Inter, Arial, sans-serif"
        fontSize="15"
        fontWeight="900"
        fill="#1688c9"
      >
        Chalapathi
      </text>
      <text
        x="60"
        y="88"
        textAnchor="middle"
        fontFamily="Inter, Arial, sans-serif"
        fontSize="5.2"
        fontWeight="700"
        fill="#5a8d86"
      >
        Institute of Engineering &amp; Technology
      </text>
      <rect x="38" y="92" width="44" height="12" rx="2" fill="#63a844" />
      <text
        x="60"
        y="100.5"
        textAnchor="middle"
        fontFamily="Inter, Arial, sans-serif"
        fontSize="6.2"
        fontWeight="900"
        fill="#fff"
      >
        AUTONOMOUS
      </text>
    </svg>
  );
}
