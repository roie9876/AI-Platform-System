export function RegionBadge({ region }: { region: string }) {
  return (
    <span className="inline-flex items-center rounded-md bg-gray-100 px-2 py-0.5 text-xs font-medium uppercase text-gray-700">
      {region}
    </span>
  );
}
