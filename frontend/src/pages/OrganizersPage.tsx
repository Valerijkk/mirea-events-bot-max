import { useState, type FormEvent } from 'react'
import {
  useCreateOrganizer,
  useDeleteOrganizer,
  useOrganizers,
  useUpdateOrganizer,
} from '../api/organizers'
import { getApiErrorMessage } from '../api/client'
import { Modal } from '../components/Modal'
import { Select } from '../components/Select'
import type { Organizer, OrganizerCreate, OrganizerRole, OrganizerUpdate } from '../types/api'
import { formatDateTime } from '../utils/format'

export function OrganizersPage() {
  const { data: organizers = [], isLoading, error } = useOrganizers()
  const createMutation = useCreateOrganizer()
  const updateMutation = useUpdateOrganizer()
  const deleteMutation = useDeleteOrganizer()

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Organizer | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<OrganizerRole>('organizer')
  const [department, setDepartment] = useState('')

  const openCreate = () => {
    setEditing(null)
    setName('')
    setEmail('')
    setPassword('')
    setRole('organizer')
    setDepartment('')
    setFormError(null)
    setModalOpen(true)
  }

  const openEdit = (org: Organizer) => {
    setEditing(org)
    setName(org.name ?? '')
    setEmail(org.email)
    setPassword('')
    setRole(org.role)
    setDepartment(org.department ?? '')
    setFormError(null)
    setModalOpen(true)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setFormError(null)
    try {
      if (editing) {
        const data: OrganizerUpdate = {
          name: name.trim() || null,
          email,
          role,
          department: department.trim() || null,
        }
        if (password) data.password = password
        await updateMutation.mutateAsync({ id: editing.id, data })
      } else {
        const data: OrganizerCreate = {
          name: name.trim() || null,
          email,
          password,
          role,
          department: department.trim() || null,
        }
        await createMutation.mutateAsync(data)
      }
      setModalOpen(false)
    } catch (err) {
      setFormError(getApiErrorMessage(err))
    }
  }

  const handleDelete = async (id: number) => {
    if (!window.confirm('Удалить организатора?')) return
    try {
      await deleteMutation.mutateAsync(id)
    } catch (err) {
      setFormError(getApiErrorMessage(err))
    }
  }

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold sm:text-2xl">Организаторы</h1>
        <button
          type="button"
          onClick={openCreate}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700"
          data-testid="btn-create-organizer"
        >
          Добавить
        </button>
      </div>

      {isLoading && <p className="text-slate-600">Загрузка…</p>}
      {error && <p className="text-red-600">{getApiErrorMessage(error)}</p>}
      {formError && !modalOpen && <p className="mb-4 text-red-600">{formError}</p>}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
        <table className="min-w-full text-sm" data-testid="organizers-table">
          <thead className="bg-slate-50 text-left text-slate-600 dark:bg-slate-800 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">Имя</th>
              <th className="hidden px-4 py-3 sm:table-cell">Email</th>
              <th className="px-4 py-3">Роль</th>
              <th className="hidden px-4 py-3 lg:table-cell">Создан</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {organizers.map((org) => (
              <tr
                key={org.id}
                className="even:bg-slate-50/50 hover:bg-slate-50 dark:even:bg-slate-800/30 dark:hover:bg-slate-800/50"
              >
                <td className="px-4 py-3 font-medium dark:text-slate-200">
                  <div>{org.name ?? '—'}</div>
                  <div className="text-xs text-slate-500 sm:hidden">{org.email}</div>
                </td>
                <td className="hidden px-4 py-3 dark:text-slate-300 sm:table-cell">{org.email}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${org.role === 'admin' ? 'bg-brand-100 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300' : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'}`}>
                    {org.role === 'admin' ? 'Админ' : 'Организатор'}
                  </span>
                </td>
                <td className="hidden px-4 py-3 text-slate-600 dark:text-slate-400 lg:table-cell">
                  {org.created_at ? formatDateTime(org.created_at) : '—'}
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={() => openEdit(org)}
                      className="text-brand-600 hover:underline dark:text-brand-400"
                      data-testid={`btn-edit-organizer-${org.id}`}
                    >
                      Изменить
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(org.id)}
                      className="text-red-600 hover:underline dark:text-red-400"
                      data-testid={`btn-delete-organizer-${org.id}`}
                    >
                      Удалить
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Modal
        open={modalOpen}
        title={editing ? 'Редактировать организатора' : 'Новый организатор'}
        onClose={() => setModalOpen(false)}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="org-name" className="mb-1 block text-sm font-medium">
              Имя
            </label>
            <input
              id="org-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              data-testid="input-organizer-name"
            />
          </div>
          <div>
            <label htmlFor="org-email" className="mb-1 block text-sm font-medium">
              Email
            </label>
            <input
              id="org-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              data-testid="input-organizer-email"
            />
          </div>
          <div>
            <label htmlFor="org-password" className="mb-1 block text-sm font-medium">
              Пароль{editing ? ' (оставьте пустым, чтобы не менять)' : ''}
            </label>
            <input
              id="org-password"
              type="password"
              required={!editing}
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              data-testid="input-organizer-password"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Роль</label>
            <Select
              value={role}
              onChange={(v) => setRole(v as OrganizerRole)}
              options={[
                { value: 'organizer', label: 'Организатор' },
                { value: 'admin',     label: 'Админ' },
              ]}
              data-testid="select-organizer-role"
            />
          </div>
          <div>
            <label htmlFor="org-department" className="mb-1 block text-sm font-medium">
              Подразделение
            </label>
            <input
              id="org-department"
              type="text"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              data-testid="input-organizer-department"
            />
          </div>
          {formError && <p className="text-sm text-red-600">{formError}</p>}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setModalOpen(false)}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending || updateMutation.isPending}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700 disabled:opacity-50"
              data-testid="btn-save-organizer"
            >
              Сохранить
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
