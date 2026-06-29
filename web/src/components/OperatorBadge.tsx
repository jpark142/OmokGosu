// A small "운영자" chip rendered next to a username when that username is a
// configured operator. Renders nothing for everyone else, so it's safe to drop
// in beside any username.

import { useIsOperator } from "@/lib/operators";

interface Props {
  username?: string | null;
  className?: string;
}

export default function OperatorBadge({ username, className = "" }: Props) {
  const isOperator = useIsOperator();
  if (!isOperator(username)) return null;
  return (
    <span
      className={`inline-flex items-center text-[10px] leading-none px-1 py-0.5 bg-rose-600 text-white rounded font-semibold shrink-0 ${className}`}
      title="운영자 계정"
    >
      운영자
    </span>
  );
}
