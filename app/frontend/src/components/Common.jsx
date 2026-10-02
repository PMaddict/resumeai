export function StatCard({ label, value, accent = 'text-gray-900' }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`mt-1.5 text-2xl font-semibold ${accent}`}>{value}</p>
    </div>
  )
}

export function EmptyState({ title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 bg-white py-14 text-center">
      <p className="text-sm font-medium text-gray-700">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-gray-400">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

const STRENGTH_STYLES = {
  strong: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  partial: 'bg-amber-50 text-amber-700 ring-amber-200',
  unsupported: 'bg-red-50 text-red-700 ring-red-200',
}

export function StrengthBadge({ strength }) {
  const style = STRENGTH_STYLES[strength] || STRENGTH_STYLES.unsupported
  const label = strength === 'strong' ? 'Strong match' : strength === 'partial' ? 'Partial match' : 'Unsupported'
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset whitespace-nowrap ${style}`}>
      {label}
    </span>
  )
}

export function PriorityBadge({ priority }) {
  const isMust = priority === 'must_have'
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset whitespace-nowrap ${
        isMust ? 'bg-gray-900 text-white ring-gray-900' : 'bg-gray-100 text-gray-600 ring-gray-200'
      }`}
    >
      {isMust ? 'Must have' : 'Nice to have'}
    </span>
  )
}

export function Spinner({ label }) {
  return (
    <div className="flex items-center gap-2 text-sm text-gray-500">
      <svg className="h-4 w-4 animate-spin text-gray-400" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
      </svg>
      {label}
    </div>
  )
}

export function Button({ children, variant = 'primary', className = '', ...props }) {
  const base = 'rounded-lg px-3.5 py-2 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed'
  const styles = {
    primary: 'bg-gray-900 text-white hover:bg-gray-800',
    secondary: 'border border-gray-200 text-gray-700 hover:bg-gray-50',
    danger: 'border border-gray-200 text-red-500 hover:bg-red-50',
  }
  return (
    <button className={`${base} ${styles[variant]} ${className}`} {...props}>
      {children}
    </button>
  )
}
