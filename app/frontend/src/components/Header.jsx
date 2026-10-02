export function Header({ title, subtitle, actions }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-gray-200 bg-white px-8 py-5">
      <div>
        <h1 className="text-lg font-semibold text-gray-900">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-gray-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}
