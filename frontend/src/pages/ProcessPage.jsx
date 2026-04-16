import { useState, useEffect, useRef } from 'react'
import {
  Upload, FolderOpen, Loader2, CheckCircle2, AlertCircle, Sparkles,
  FileAudio, Play, Pause, Tag, Search, Clock, Database,
  ChevronRight, Music, Headphones
} from 'lucide-react'
import { useTranslation } from '../i18n/useTranslation'
import { useApi } from '../hooks/useApi'
import { useToast } from '../hooks/useToast'
import { useProcessing } from '../hooks/useProcessing'

export default function ProcessPage({ onNavigate }) {
  const { t } = useTranslation()
  const api = useApi()
  const toast = useToast()
  const proc = useProcessing()
  const fileInput = useRef(null)

  // State
  const [mode, setMode] = useState('upload') // 'upload' | 'batch'
  const [categories, setCategories] = useState([])
  const [selectedCats, setSelectedCats] = useState([])

  // Upload state
  const [file, setFile] = useState(null)
  const [fileUrl, setFileUrl] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [dragOver, setDragOver] = useState(false)

  // Batch state
  const [volumePath, setVolumePath] = useState('/Volumes/serverless_stable_jsf_catalog/audio_insight_hub/sample_audios')
  const [volumeFiles, setVolumeFiles] = useState(null)
  const [loadingFiles, setLoadingFiles] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [batchResults, setBatchResults] = useState(null)
  const [playingPath, setPlayingPath] = useState(null)
  const [selectedFiles, setSelectedFiles] = useState(new Set())
  const [fileSearch, setFileSearch] = useState('')

  // Audio player
  const audioRef = useRef(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  useEffect(() => {
    api.fetchCategories().then(setCategories).catch(console.error)
  }, [])

  // Cleanup file URL on unmount
  useEffect(() => {
    return () => { if (fileUrl) URL.revokeObjectURL(fileUrl) }
  }, [fileUrl])

  const toggleCategory = (id) => {
    setSelectedCats(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const selectAllCats = () => {
    if (selectedCats.length === categories.length) setSelectedCats([])
    else setSelectedCats(categories.map(c => c.id))
  }

  // ---- Upload handlers ----
  const handleFile = (f) => {
    if (!f) return
    setFile(f)
    if (fileUrl) URL.revokeObjectURL(fileUrl)
    setFileUrl(URL.createObjectURL(f))
    setResult(null)
    setError(null)
  }

  const handleDrop = (e) => {
    e.preventDefault(); setDragOver(false)
    handleFile(e.dataTransfer?.files?.[0])
  }

  const processUpload = async () => {
    if (!file) return
    setUploading(true); setProgress(0); setStage(t('upload.transcribing')); setResult(null); setError(null)
    try {
      const data = await api.uploadAudio(file, selectedCats, (pct) => {
        setProgress(pct)
        if (pct === 100) setStage(t('upload.analyzing'))
      })
      setResult(data)
      toast.success(t('upload.success'))
    } catch (err) {
      setError(err.message)
      toast.error(`${t('upload.error')}: ${err.message}`)
    } finally {
      setUploading(false)
    }
  }

  // ---- Batch handlers ----
  const loadVolumeFiles = async () => {
    if (!volumePath.trim()) return
    setLoadingFiles(true); setVolumeFiles(null); setSelectedFiles(new Set()); setFileSearch('')
    try {
      const data = await api.listVolumeFiles(volumePath.trim())
      setVolumeFiles(data)
      setSelectedFiles(new Set(data.files.map(f => f.name)))
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoadingFiles(false)
    }
  }

  const toggleFile = (name) => {
    setSelectedFiles(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name); else next.add(name)
      return next
    })
  }

  const toggleAllFiles = () => {
    if (!volumeFiles) return
    const filtered = filteredVolumeFiles()
    if (filtered.every(f => selectedFiles.has(f.name))) {
      setSelectedFiles(prev => {
        const next = new Set(prev)
        filtered.forEach(f => next.delete(f.name))
        return next
      })
    } else {
      setSelectedFiles(prev => {
        const next = new Set(prev)
        filtered.forEach(f => next.add(f.name))
        return next
      })
    }
  }

  const filteredVolumeFiles = () => {
    if (!volumeFiles) return []
    if (!fileSearch.trim()) return volumeFiles.files
    const q = fileSearch.toLowerCase()
    return volumeFiles.files.filter(f => f.name.toLowerCase().includes(q))
  }

  const processBatch = () => {
    if (!volumePath.trim() || selectedFiles.size === 0) {
      toast.error('Selecione pelo menos um audio'); return
    }

    const files = [...selectedFiles]
    proc.startProcessing(files)

    // Navigate FIRST, then fire-and-forget the SSE
    onNavigate('processing')

    // Run SSE in background — NOT awaited, so UI stays free
    api.processBatchSSE(volumePath.trim(), selectedCats, files, (event) => {
      if (event.type === 'status') {
        proc.updateFile(event.file, { status: 'processing', stage: event.stage, message: event.message })
      } else if (event.type === 'completed') {
        proc.updateFile(event.file, { status: 'done', stage: 'done', message: 'Concluido!', result: event.result })
      } else if (event.type === 'error') {
        proc.updateFile(event.file, { status: 'error', stage: 'error', message: event.error })
      } else if (event.type === 'done') {
        proc.finishProcessing(event)
      }
    }).catch((err) => {
      proc.finishProcessing({ processed: 0, errors: files.length })
    })
  }

  const playVolumeAudio = (path) => {
    if (playingPath === path) {
      if (audioRef.current) { audioRef.current.pause(); setIsPlaying(false) }
      setPlayingPath(null)
      return
    }
    setPlayingPath(path)
    const url = api.getAudioStreamUrl(path)
    if (audioRef.current) {
      audioRef.current.src = url
      audioRef.current.play().then(() => setIsPlaying(true)).catch(console.error)
    }
  }

  // ---- Player controls ----
  const togglePlay = () => {
    if (!audioRef.current) return
    if (isPlaying) { audioRef.current.pause(); setIsPlaying(false) }
    else audioRef.current.play().then(() => setIsPlaying(true)).catch(console.error)
  }

  const seekTo = (e) => {
    if (!audioRef.current || !duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    const pct = (e.clientX - rect.left) / rect.width
    audioRef.current.currentTime = pct * duration
  }

  const formatTime = (s) => {
    if (!s || isNaN(s)) return '0:00'
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  const sentColor = { positive: 'text-green-500', negative: 'text-red-500', neutral: 'text-gray-500' }

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-[fadeIn_0.3s_ease-out]">
      {/* Hidden audio element */}
      <audio
        ref={audioRef}
        onTimeUpdate={() => setCurrentTime(audioRef.current?.currentTime || 0)}
        onLoadedMetadata={() => setDuration(audioRef.current?.duration || 0)}
        onEnded={() => { setIsPlaying(false); setPlayingPath(null) }}
      />

      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          {t('upload.title')}
        </h1>
        <p className="mt-1 text-gray-500">{t('app.subtitle')}</p>
      </div>

      {/* Mode switcher */}
      <div className="glass-card p-1.5 flex gap-1">
        <button
          onClick={() => setMode('upload')}
          className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl font-semibold text-sm transition-all ${
            mode === 'upload'
              ? 'gradient-bg text-white shadow-lg shadow-brand-500/25'
              : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
          }`}
        >
          <Upload className="w-4 h-4" />
          Upload Individual
        </button>
        <button
          onClick={() => setMode('batch')}
          className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl font-semibold text-sm transition-all ${
            mode === 'batch'
              ? 'gradient-bg text-white shadow-lg shadow-brand-500/25'
              : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
          }`}
        >
          <FolderOpen className="w-4 h-4" />
          Batch (Volume)
        </button>
      </div>

      {/* Category selector */}
      <div className="glass-card p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Tag className="w-4 h-4 text-brand-500" />
            <span className="font-semibold text-sm text-gray-700 dark:text-gray-300">
              Categorias para classificacao
            </span>
          </div>
          <button
            onClick={selectAllCats}
            className="text-xs font-medium text-brand-500 hover:text-brand-600 transition-colors"
          >
            {selectedCats.length === categories.length ? 'Desmarcar todas' : 'Selecionar todas'}
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {categories.map((cat) => {
            const active = selectedCats.includes(cat.id)
            return (
              <button
                key={cat.id}
                onClick={() => toggleCategory(cat.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border ${
                  active
                    ? 'border-transparent text-white shadow-sm scale-105'
                    : 'border-gray-200 dark:border-gray-700 text-gray-500 hover:border-gray-300'
                }`}
                style={active ? { backgroundColor: cat.color } : {}}
              >
                {cat.name}
              </button>
            )
          })}
        </div>
        {selectedCats.length === 0 && (
          <p className="text-xs text-gray-400 mt-2">Nenhuma selecionada = todas as categorias serao usadas</p>
        )}
      </div>

      {/* ===== UPLOAD MODE ===== */}
      {mode === 'upload' && (
        <div className="space-y-4">
          {/* Dropzone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => !uploading && fileInput.current?.click()}
            className={`relative overflow-hidden rounded-2xl border-2 border-dashed p-8 text-center cursor-pointer transition-all duration-300
              ${dragOver ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/10 scale-[1.01]' : 'border-gray-300 dark:border-gray-700 hover:border-brand-400'}
              ${uploading ? 'pointer-events-none opacity-60' : ''}`}
          >
            <input ref={fileInput} type="file" className="hidden" accept="audio/*" onChange={(e) => handleFile(e.target.files?.[0])} />
            <div className="absolute inset-0 opacity-5 flex items-center justify-center gap-1">
              {[...Array(16)].map((_, i) => (
                <div key={i} className="w-1 bg-brand-500 rounded-full wave-animation"
                  style={{ height: `${15 + Math.random() * 30}px`, animationDelay: `${i * 0.1}s` }} />
              ))}
            </div>
            <div className="relative z-10">
              {file && !uploading ? (
                <div className="flex items-center gap-4">
                  <div className="w-14 h-14 rounded-xl bg-brand-100 dark:bg-brand-500/20 flex items-center justify-center">
                    <Music className="w-7 h-7 text-brand-500" />
                  </div>
                  <div className="text-left flex-1">
                    <p className="font-semibold text-gray-800 dark:text-gray-200">{file.name}</p>
                    <p className="text-sm text-gray-400">{(file.size / 1024).toFixed(0)} KB</p>
                  </div>
                  <span className="text-xs text-brand-500 font-medium">Trocar arquivo</span>
                </div>
              ) : uploading ? (
                <div className="space-y-3">
                  <Loader2 className="w-10 h-10 text-brand-500 animate-spin mx-auto" />
                  <p className="font-semibold text-gray-700 dark:text-gray-300">{stage}</p>
                  <div className="max-w-xs mx-auto h-2 bg-gray-200 dark:bg-gray-800 rounded-full overflow-hidden">
                    <div className="h-full gradient-bg rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
                  </div>
                </div>
              ) : (
                <>
                  <Upload className="w-10 h-10 text-brand-400 mx-auto mb-3" />
                  <p className="font-semibold text-gray-600 dark:text-gray-400">
                    {dragOver ? t('upload.dropHere') : t('upload.selectFile')}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">{t('upload.supported')}</p>
                </>
              )}
            </div>
          </div>

          {/* Player for selected file */}
          {fileUrl && !uploading && (
            <div className="glass-card p-4">
              <div className="flex items-center gap-4">
                <button onClick={togglePlay}
                  className="w-10 h-10 rounded-full gradient-bg flex items-center justify-center text-white shadow-lg shadow-brand-500/25 hover:scale-105 transition-transform">
                  {isPlaying && !playingPath ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
                </button>
                <div className="flex-1">
                  <div className="h-2 bg-gray-200 dark:bg-gray-800 rounded-full cursor-pointer overflow-hidden"
                    onClick={(e) => {
                      if (!audioRef.current) { audioRef.current.src = fileUrl }
                      seekTo(e)
                    }}>
                    <div className="h-full gradient-bg rounded-full transition-all"
                      style={{ width: duration ? `${(currentTime / duration) * 100}%` : '0%' }} />
                  </div>
                  <div className="flex justify-between mt-1 text-xs text-gray-400">
                    <span>{formatTime(currentTime)}</span>
                    <span>{formatTime(duration)}</span>
                  </div>
                </div>
              </div>
              {/* Auto-set audio src for local file */}
              {fileUrl && !playingPath && audioRef.current && audioRef.current.src !== fileUrl && (() => { audioRef.current.src = fileUrl; return null })()}
            </div>
          )}

          {/* Process button */}
          {file && !uploading && !result && (
            <button onClick={processUpload} className="btn-primary w-full flex items-center justify-center gap-2">
              <Sparkles className="w-5 h-5" />
              Processar Audio com IA
            </button>
          )}

          {/* Result */}
          {result && (
            <div className="glass-card p-5 space-y-4 animate-[slideIn_0.3s_ease-out]">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="w-6 h-6 text-green-500" />
                <div>
                  <h3 className="font-semibold text-gray-800 dark:text-gray-200">{t('upload.success')}</h3>
                  <p className="text-sm text-gray-500">{result.file_name}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: t('analyses.sentiment'), value: result.sentiment?.toUpperCase(), cls: sentColor[result.sentiment] },
                  { label: t('analyses.urgency'), value: result.urgency_level?.toUpperCase() },
                  { label: 'Categoria', value: result.category_name },
                  { label: t('analyses.language'), value: result.language_detected?.toUpperCase() },
                ].map((item, i) => (
                  <div key={i} className="p-3 rounded-xl bg-gray-50 dark:bg-gray-800/50">
                    <p className="text-xs text-gray-400 mb-1">{item.label}</p>
                    <p className={`font-semibold text-sm ${item.cls || 'text-gray-700 dark:text-gray-300'}`}>{item.value || 'N/A'}</p>
                  </div>
                ))}
              </div>
              {result.summary && <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">{result.summary}</p>}
              <button onClick={() => onNavigate('detail', result.id)} className="btn-primary w-full text-center">
                {t('analyses.viewDetails')}
              </button>
            </div>
          )}

          {error && (
            <div className="glass-card p-4 border-red-200 dark:border-red-500/20">
              <div className="flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
                <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ===== BATCH MODE ===== */}
      {mode === 'batch' && (
        <div className="space-y-4">
          {/* Volume path */}
          <div className="glass-card p-5">
            <div className="flex items-center gap-2 mb-3">
              <FolderOpen className="w-4 h-4 text-brand-500" />
              <span className="font-semibold text-sm text-gray-700 dark:text-gray-300">{t('volume.pathLabel')}</span>
            </div>
            <div className="flex gap-2">
              <input
                type="text" value={volumePath} onChange={(e) => setVolumePath(e.target.value)}
                placeholder={t('volume.pathPlaceholder')}
                className="input-field flex-1"
                onKeyDown={(e) => e.key === 'Enter' && loadVolumeFiles()}
              />
              <button onClick={loadVolumeFiles} disabled={loadingFiles || !volumePath.trim()}
                className="btn-secondary flex items-center gap-2 !px-4 disabled:opacity-50">
                {loadingFiles ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                Listar
              </button>
            </div>
          </div>

          {/* Volume file list with player */}
          {volumeFiles && (
            <div className="glass-card p-5 space-y-3 animate-[fadeIn_0.2s_ease-out]">
              {/* Header: count + search + select all */}
              <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                <div className="flex items-center gap-2">
                  <Headphones className="w-4 h-4 text-brand-500" />
                  <span className="font-semibold text-sm text-gray-700 dark:text-gray-300">
                    {selectedFiles.size}/{volumeFiles.total} selecionados
                  </span>
                </div>
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input type="text" value={fileSearch} onChange={(e) => setFileSearch(e.target.value)}
                    placeholder="Buscar audio..." className="input-field !py-2 pl-9 text-sm" />
                </div>
                <button onClick={toggleAllFiles}
                  className="btn-secondary !py-2 !px-3 text-xs whitespace-nowrap">
                  {filteredVolumeFiles().every(f => selectedFiles.has(f.name)) ? 'Desmarcar' : 'Selecionar'} todos
                </button>
              </div>

              <div className="space-y-1.5 max-h-72 overflow-y-auto">
                {filteredVolumeFiles().map((f, i) => {
                  const checked = selectedFiles.has(f.name)
                  return (
                    <div key={i} className={`flex items-center gap-3 p-3 rounded-xl transition-all
                      ${playingPath === f.path
                        ? 'bg-brand-50 dark:bg-brand-500/10 ring-1 ring-brand-500/30'
                        : checked ? 'bg-gray-50 dark:bg-gray-800/50' : 'bg-gray-50/50 dark:bg-gray-800/30 opacity-60'}`}>
                      {/* Checkbox */}
                      <button onClick={() => toggleFile(f.name)}
                        className={`w-5 h-5 rounded-md border-2 flex items-center justify-center flex-shrink-0 transition-all
                          ${checked ? 'bg-brand-500 border-brand-500 text-white' : 'border-gray-300 dark:border-gray-600'}`}>
                        {checked && <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>}
                      </button>

                      {/* Play button */}
                      <button onClick={() => playVolumeAudio(f.path)}
                        className={`w-8 h-8 rounded-lg flex items-center justify-center transition-all flex-shrink-0
                          ${playingPath === f.path ? 'gradient-bg text-white' : 'bg-gray-200 dark:bg-gray-700 text-gray-500 hover:bg-gray-300'}`}>
                        {playingPath === f.path && isPlaying
                          ? <Pause className="w-3.5 h-3.5" />
                          : <Play className="w-3.5 h-3.5 ml-0.5" />}
                      </button>

                      <div className="flex-1 min-w-0 cursor-pointer" onClick={() => toggleFile(f.name)}>
                        <p className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate">{f.name}</p>
                        {f.size && <p className="text-xs text-gray-400">{(f.size / 1024).toFixed(0)} KB</p>}
                      </div>

                      {playingPath === f.path && (
                        <div className="flex gap-0.5">
                          {[...Array(4)].map((_, j) => (
                            <div key={j} className="w-1 bg-brand-500 rounded-full wave-animation"
                              style={{ height: `${8 + Math.random() * 12}px`, animationDelay: `${j * 0.15}s` }} />
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Player bar */}
              {playingPath && (
                <div className="pt-3 border-t border-gray-200 dark:border-gray-800">
                  <div className="flex items-center gap-3">
                    <button onClick={togglePlay}
                      className="w-8 h-8 rounded-full gradient-bg flex items-center justify-center text-white shadow-sm">
                      {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 ml-0.5" />}
                    </button>
                    <div className="flex-1">
                      <div className="h-1.5 bg-gray-200 dark:bg-gray-800 rounded-full cursor-pointer overflow-hidden" onClick={seekTo}>
                        <div className="h-full gradient-bg rounded-full transition-all"
                          style={{ width: duration ? `${(currentTime / duration) * 100}%` : '0%' }} />
                      </div>
                    </div>
                    <span className="text-xs text-gray-400 font-mono w-16 text-right">
                      {formatTime(currentTime)}/{formatTime(duration)}
                    </span>
                  </div>
                </div>
              )}

              {/* Process button */}
              <button onClick={processBatch} disabled={processing || selectedFiles.size === 0}
                className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50">
                {processing ? (
                  <><Loader2 className="w-5 h-5 animate-spin" />{t('volume.processing')}</>
                ) : (
                  <><Sparkles className="w-5 h-5" />Processar {selectedFiles.size} audio{selectedFiles.size !== 1 ? 's' : ''} com IA</>
                )}
              </button>
            </div>
          )}

          {/* Link to processing status if running */}
          {proc.isRunning && (
            <button onClick={() => onNavigate('processing')}
              className="glass-card p-4 w-full flex items-center gap-3 hover:shadow-lg transition-all cursor-pointer">
              <Loader2 className="w-5 h-5 text-brand-500 animate-spin" />
              <span className="font-medium text-brand-600 dark:text-brand-400">Processamento em andamento — clique para acompanhar</span>
              <ChevronRight className="w-4 h-4 text-gray-400 ml-auto" />
            </button>
          )}
        </div>
      )}
    </div>
  )
}
