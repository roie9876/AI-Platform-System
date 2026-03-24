"use client";

interface FilterOption {
  label: string;
  value: string;
}

interface FilterBarProps {
  filters: Array<{
    name: string;
    options: FilterOption[];
    value: string;
    onChange: (value: string) => void;
  }>;
  sortOptions?: FilterOption[];
  sortValue?: string;
  onSortChange?: (value: string) => void;
}

export function FilterBar({
  filters,
  sortOptions,
  sortValue,
  onSortChange,
}: FilterBarProps) {
  return (
    <div className="flex items-center gap-2 bg-white">
      {filters.map((filter) => (
        <select
          key={filter.name}
          value={filter.value}
          onChange={(e) => filter.onChange(e.target.value)}
          className="h-9 rounded-md border border-gray-200 bg-white px-3 text-sm text-gray-700 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
        >
          {filter.options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      ))}
      {sortOptions && (
        <select
          value={sortValue}
          onChange={(e) => onSortChange?.(e.target.value)}
          className="ml-auto h-9 rounded-md border border-gray-200 bg-white px-3 text-sm text-gray-700 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
        >
          {sortOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}
