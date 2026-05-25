interface PaginationProps {
  page: number
  pages: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, pages, onPageChange }: PaginationProps) {
  if (pages <= 1) return null

  return (
    <nav className="flex items-center justify-center gap-2" aria-label="Пагинация">
      <button
        type="button"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
        className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-slate-50"
        data-testid="pagination-prev"
      >
        Назад
      </button>
      <span className="text-sm text-slate-600">
        {page} / {pages}
      </span>
      <button
        type="button"
        disabled={page >= pages}
        onClick={() => onPageChange(page + 1)}
        className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-slate-50"
        data-testid="pagination-next"
      >
        Вперёд
      </button>
    </nav>
  )
}
