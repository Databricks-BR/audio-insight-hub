import { useState, useEffect } from 'react'
import {
  Settings, Tag, Plus, Trash2, Edit3, Save, X, Globe,
  Moon, Sun, Info, CheckCircle2, Cpu, AlertTriangle, Database
} from 'lucide-react'
import { useTranslation } from '../i18n/useTranslation'
import { useApi } from '../hooks/useApi'
import { useToast } from '../hooks/useToast'

const PRESET_COLORS = [
  '#ef4444', '#f59e0b', '#22c55e', '#3b82f6', '#8b5cf6',
  '#ec4899', '#06b6d4', '#6366f1', '#14b8a6', '#f97316',
  '#dc2626', '#84cc16',
]

export default function SettingsPage() {
  const { t, locale, changeLocale } = useTranslation()
  const api = useApi()
  const toast = useToast()
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState(null)
  const [editData, setEditData] = useState({ name: '', color: '#6366f1' })
  const [showAdd, setShowAdd] = useState(false)
  const [newCat, setNewCat] = useState({ name: '', color: '#6366f1' })
  const [dark, setDark] = useState(document.documentElement.classList.contains('dark'))

  // Model config
  const [models, setModels] = useState([])
  const [selectedModel, setSelectedModel] = useState('')
  const [loadingModels, setLoadingModels] = useState(true)

  // Clear DB
  const [clearing, setClearing] = useState(false)

  const loadCategories = async () => {
    try { setCategories(await api.fetchCategories()) } catch (err) { console.error(err) } finally { setLoading(false) }
  }

  const loadModels = async () => {
    setLoadingModels(true)
    try {
      const [modelsData, settings] = await Promise.all([api.fetchModels(), api.fetchSettings()])
      setModels(modelsData)
      setSelectedModel(settings.llm_model || 'databricks-claude-sonnet-4-6')
    } catch (err) { console.error(err) } finally { setLoadingModels(false) }
  }

  useEffect(() => { loadCategories(); loadModels() }, [])

  const handleAdd = async () => {
    if (!newCat.name.trim()) return
    try {
      await api.createCategory(newCat)
      toast.success('Categoria criada')
      setNewCat({ name: '', color: '#6366f1' }); setShowAdd(false); loadCategories()
    } catch (err) { toast.error(err.message) }
  }

  const handleUpdate = async (id) => {
    try {
      await api.updateCategory(id, editData)
      toast.success('Atualizado'); setEditingId(null); loadCategories()
    } catch (err) { toast.error(err.message) }
  }

  const handleDelete = async (id) => {
    if (!confirm('Excluir esta categoria?')) return
    try { await api.deleteCategory(id); toast.success('Excluido'); loadCategories() } catch (err) { toast.error(err.message) }
  }

  const handleModelChange = async (model) => {
    setSelectedModel(model)
    try {
      await api.updateSetting('llm_model', model)
      toast.success(`Modelo alterado para ${model}`)
    } catch (err) { toast.error(err.message) }
  }

  const handleClearAll = async () => {
    if (!confirm('Tem certeza que deseja EXCLUIR TODAS as analises? Esta acao nao pode ser desfeita.')) return
    setClearing(true)
    try {
      await api.deleteAllAnalyses()
      toast.success('Todas as analises foram excluidas')
    } catch (err) { toast.error(err.message) } finally { setClearing(false) }
  }

  const toggleDark = () => {
    const next = !dark; setDark(next)
    localStorage.setItem('aih-dark', String(next))
    document.documentElement.classList.toggle('dark', next)
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-[fadeIn_0.3s_ease-out]">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white">{t('settings.title')}</h1>

      {/* Model Configuration */}
      <div className="glass-card p-6">
        <div className="flex items-center gap-2 mb-5">
          <Cpu className="w-5 h-5 text-brand-500" />
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">Modelo de IA</h2>
        </div>
        {loadingModels ? (
          <div className="h-12 shimmer rounded-xl" />
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-gray-500">Modelo usado para analise de sentimento, categorizacao e resumo:</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {models.map((m) => (
                <button
                  key={m.name}
                  onClick={() => handleModelChange(m.name)}
                  className={`flex items-center gap-3 p-3 rounded-xl text-left transition-all border ${
                    selectedModel === m.name
                      ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/10 ring-1 ring-brand-500/30'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  }`}
                >
                  <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                    m.state === 'READY' ? 'bg-green-500' : 'bg-yellow-500'
                  }`} />
                  <div className="min-w-0">
                    <p className={`text-sm font-medium truncate ${
                      selectedModel === m.name ? 'text-brand-600 dark:text-brand-400' : 'text-gray-700 dark:text-gray-300'
                    }`}>
                      {m.name.replace('databricks-', '')}
                    </p>
                    <p className="text-xs text-gray-400">{m.state}</p>
                  </div>
                  {selectedModel === m.name && (
                    <CheckCircle2 className="w-4 h-4 text-brand-500 ml-auto flex-shrink-0" />
                  )}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-400">Modelo atual: <span className="font-mono text-brand-500">{selectedModel}</span></p>
          </div>
        )}
      </div>

      {/* General Settings */}
      <div className="glass-card p-6">
        <div className="flex items-center gap-2 mb-5">
          <Settings className="w-5 h-5 text-brand-500" />
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">{t('settings.general')}</h2>
        </div>
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Globe className="w-5 h-5 text-gray-400" />
              <span className="text-gray-700 dark:text-gray-300">{t('settings.language')}</span>
            </div>
            <div className="flex gap-2">
              {[{ code: 'pt', label: 'Portugues' }, { code: 'en', label: 'English' }, { code: 'es', label: 'Espanol' }].map((lang) => (
                <button key={lang.code} onClick={() => changeLocale(lang.code)}
                  className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                    locale === lang.code
                      ? 'gradient-bg text-white shadow-lg shadow-brand-500/25'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
                  }`}>{lang.label}</button>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {dark ? <Moon className="w-5 h-5 text-gray-400" /> : <Sun className="w-5 h-5 text-gray-400" />}
              <span className="text-gray-700 dark:text-gray-300">{t('settings.theme')}</span>
            </div>
            <button onClick={toggleDark}
              className={`relative w-14 h-7 rounded-full transition-colors ${dark ? 'bg-brand-500' : 'bg-gray-300'}`}>
              <div className={`absolute top-0.5 left-0.5 w-6 h-6 rounded-full bg-white shadow-md transition-transform ${dark ? 'translate-x-7' : 'translate-x-0'}`} />
            </button>
          </div>
        </div>
      </div>

      {/* Categories */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <Tag className="w-5 h-5 text-brand-500" />
            <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">{t('settings.categories')}</h2>
          </div>
          <button onClick={() => setShowAdd(!showAdd)} className="btn-primary flex items-center gap-2 !py-2 !px-4 text-sm">
            <Plus className="w-4 h-4" /> {t('settings.addCategory')}
          </button>
        </div>

        {showAdd && (
          <div className="mb-4 p-4 rounded-xl bg-brand-50 dark:bg-brand-500/10 border border-brand-200 dark:border-brand-500/20 animate-[slideIn_0.2s_ease-out]">
            <div className="flex flex-col sm:flex-row gap-3">
              <input type="text" value={newCat.name} onChange={(e) => setNewCat({ ...newCat, name: e.target.value })}
                placeholder={t('settings.categoryName')} className="input-field flex-1"
                onKeyDown={(e) => e.key === 'Enter' && handleAdd()} />
              <div className="flex items-center gap-1 flex-wrap">
                {PRESET_COLORS.map((color) => (
                  <button key={color} onClick={() => setNewCat({ ...newCat, color })}
                    className={`w-6 h-6 rounded-full transition-transform ${newCat.color === color ? 'scale-125 ring-2 ring-offset-2 ring-brand-500' : 'hover:scale-110'}`}
                    style={{ backgroundColor: color }} />
                ))}
              </div>
              <div className="flex gap-2">
                <button onClick={handleAdd} className="btn-primary !py-2 !px-4 text-sm"><Save className="w-4 h-4" /></button>
                <button onClick={() => setShowAdd(false)} className="btn-secondary !py-2 !px-4 text-sm"><X className="w-4 h-4" /></button>
              </div>
            </div>
          </div>
        )}

        <div className="space-y-2">
          {loading ? [1, 2, 3].map((i) => <div key={i} className="h-14 rounded-xl shimmer" />) : categories.map((cat) => (
            <div key={cat.id} className="flex items-center gap-3 p-4 rounded-xl bg-gray-50 dark:bg-gray-800/50 group">
              <div className="w-4 h-4 rounded-full flex-shrink-0" style={{ backgroundColor: cat.color }} />
              {editingId === cat.id ? (
                <div className="flex-1 flex flex-col sm:flex-row gap-2">
                  <input type="text" value={editData.name} onChange={(e) => setEditData({ ...editData, name: e.target.value })}
                    className="input-field flex-1 !py-2" onKeyDown={(e) => e.key === 'Enter' && handleUpdate(cat.id)} />
                  <div className="flex gap-1 flex-wrap">
                    {PRESET_COLORS.map((color) => (
                      <button key={color} onClick={() => setEditData({ ...editData, color })}
                        className={`w-5 h-5 rounded-full transition-transform ${editData.color === color ? 'scale-125 ring-2 ring-brand-500' : 'hover:scale-110'}`}
                        style={{ backgroundColor: color }} />
                    ))}
                  </div>
                  <div className="flex gap-1">
                    <button onClick={() => handleUpdate(cat.id)} className="p-2 rounded-lg bg-green-100 text-green-600 hover:bg-green-200"><CheckCircle2 className="w-4 h-4" /></button>
                    <button onClick={() => setEditingId(null)} className="p-2 rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200"><X className="w-4 h-4" /></button>
                  </div>
                </div>
              ) : (
                <>
                  <span className="flex-1 font-medium text-gray-700 dark:text-gray-300">{cat.name}</span>
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onClick={() => { setEditingId(cat.id); setEditData({ name: cat.name, color: cat.color }) }}
                      className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400 hover:text-brand-500"><Edit3 className="w-4 h-4" /></button>
                    <button onClick={() => handleDelete(cat.id)}
                      className="p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-500/10 text-gray-400 hover:text-red-500"><Trash2 className="w-4 h-4" /></button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Danger Zone */}
      <div className="glass-card p-6 border border-red-200 dark:border-red-500/20">
        <div className="flex items-center gap-2 mb-4">
          <AlertTriangle className="w-5 h-5 text-red-500" />
          <h2 className="text-lg font-semibold text-red-600 dark:text-red-400">Zona de Perigo</h2>
        </div>
        <div className="flex items-center justify-between p-4 rounded-xl bg-red-50 dark:bg-red-500/5">
          <div>
            <p className="font-medium text-gray-800 dark:text-gray-200">Limpar todas as analises</p>
            <p className="text-sm text-gray-500">Remove permanentemente todas as analises do banco de dados.</p>
          </div>
          <button
            onClick={handleClearAll}
            disabled={clearing}
            className="px-5 py-2.5 rounded-xl font-semibold text-white bg-red-500 hover:bg-red-600 shadow-lg shadow-red-500/25 transition-all disabled:opacity-50 flex items-center gap-2"
          >
            {clearing ? (
              <><Database className="w-4 h-4 animate-spin" /> Limpando...</>
            ) : (
              <><Trash2 className="w-4 h-4" /> Limpar Base</>
            )}
          </button>
        </div>
      </div>

      {/* About */}
      <div className="glass-card p-6">
        <div className="flex items-center gap-2 mb-4">
          <Info className="w-5 h-5 text-brand-500" />
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">{t('settings.about')}</h2>
        </div>
        <div className="space-y-2 text-sm text-gray-500 dark:text-gray-400">
          <p><strong>Audio Insight Hub</strong> v1.0.0</p>
          <p>Powered by Databricks Foundation Model API + Lakebase</p>
          <p>Transcricao: Google Speech Recognition | Analise: {selectedModel}</p>
        </div>
      </div>
    </div>
  )
}
