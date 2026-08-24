import { Spinner } from "@/components/ui/spinner";

export default function Loading() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center" aria-busy>
      <Spinner label="Loading the page" />
    </div>
  );
}
