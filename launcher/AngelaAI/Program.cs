// Executável próprio: o mesmo CPython e pacotes da instalação atual,
// mas com identidade de processo Ângela AI para o Windows.
// A câmera continua obedecendo ao consentimento da aplicação Python.
using System;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;

internal static class Program
{
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int PythonMain(int argc, IntPtr argv);

    private static string? FindProject()
    {
        DirectoryInfo? directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null)
        {
            if (File.Exists(Path.Combine(directory.FullName, "angela", "desktop_overlay.py")))
                return directory.FullName;
            directory = directory.Parent;
        }
        return null;
    }

    private static string PythonHome()
    {
        string? overrideHome = Environment.GetEnvironmentVariable("ANGELA_PYTHON_HOME");
        if (!string.IsNullOrWhiteSpace(overrideHome))
            return Path.GetFullPath(overrideHome);

        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        return Path.Combine(local, "Programs", "Python", "Python312");
    }

    public static int Main(string[] args)
    {
        if (args.Contains("--launcher-info"))
        {
            Console.WriteLine("APP=Ângela AI; HOST=CPython 3.12");
            return 0;
        }

        string? project = FindProject();
        if (project is null)
        {
            Console.Error.WriteLine("Não encontrei o projeto Ângela AI.");
            return 2;
        }

        string home = PythonHome();
        string dll = Path.Combine(home, "python312.dll");
        if (!File.Exists(dll) || !Directory.Exists(Path.Combine(home, "Lib")))
        {
            Console.Error.WriteLine("Python 3.12 não está instalado no local configurado.");
            return 3;
        }

        // Não muda instalações globais, chaves de registro ou permissões.
        // Usa o runtime e os mesmos pacotes já testados no Windows.
        Environment.SetEnvironmentVariable("PYTHONHOME", home);
        Environment.SetEnvironmentVariable("PYTHONIOENCODING", "utf-8");
        Directory.SetCurrentDirectory(project);

        // O Py_Main pode criar sua propria tabela de ambiente no Windows.
        // Definir somente a variavel pelo host .NET nao garante que Python
        // a enxergue. No modo atalho, definimos a configuracao em os.environ
        // antes de importar o HUD. Com argumentos, manter o Python intacto.
        string[] parameters = args.Length == 0
            ? new[] { "-c", "import os;os.environ['ANGELA_ENABLE_VOICE']='1';from angela.desktop_overlay import main;main()" }
            : args;

        // Ao abrir pelo atalho (sem argumentos), a escuta deve iniciar sempre.
        // Com parametros explicitos (-m/-c), preservar o modo de teste.
        if (args.Length == 0)
            Environment.SetEnvironmentVariable("ANGELA_ENABLE_VOICE", "1");

        // Python executado dentro deste processo, NÃO subprocesso python.exe.
        // Assim é o executável ÂngelaAI.exe que usa o microfone.
        IntPtr library = IntPtr.Zero;
        IntPtr argv = IntPtr.Zero;
        IntPtr[] strings = Array.Empty<IntPtr>();
        try
        {
            library = NativeLibrary.Load(dll);
            IntPtr fn = NativeLibrary.GetExport(library, "Py_Main");
            PythonMain pythonMain = Marshal.GetDelegateForFunctionPointer<PythonMain>(fn);
            string[] all = (new[] { Environment.ProcessPath ?? "AngelaAI.exe" })
                .Concat(parameters).ToArray();
            strings = all.Select(Marshal.StringToHGlobalUni).ToArray();
            argv = Marshal.AllocHGlobal(IntPtr.Size * strings.Length);
            for (int i = 0; i < strings.Length; i++)
                Marshal.WriteIntPtr(argv, i * IntPtr.Size, strings[i]);
            return pythonMain(strings.Length, argv);
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine("Falha no inicializador Ângela AI: " + exception.GetType().Name);
            return 4;
        }
        finally
        {
            if (argv != IntPtr.Zero)
                Marshal.FreeHGlobal(argv);
            foreach (IntPtr arg in strings)
                if (arg != IntPtr.Zero)
                    Marshal.FreeHGlobal(arg);
            if (library != IntPtr.Zero)
                NativeLibrary.Free(library);
        }
    }
}
