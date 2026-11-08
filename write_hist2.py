content2 = r'''
      </div>
'''
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Clock className="w-5 h-5 text-slate-500" />
          <h3 className="text-lg font-semibold text-slate-900">Biblioteca de imágenes</h3>
        </div>
        <button
          onClick={fetchTasks}
          disabled={loading}
          className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 disabled:opacity-50 flex items-center gap-1"
        >
          <RotateCcw className="w-4 h-4" />
          Actualizar
        </button>
      </div>
'''