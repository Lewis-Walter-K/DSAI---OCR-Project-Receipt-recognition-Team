import React, { useRef } from 'react';
import { Camera, ImagePlus, ScanLine } from 'lucide-react';

interface CaptureProps {
  onImageCaptured: (file: File) => void;
}

const Capture: React.FC<CaptureProps> = ({ onImageCaptured }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      onImageCaptured(file);
    }
  };

  const triggerUpload = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-144px)] px-6 pb-12 relative overflow-hidden bg-white">
      {/* Decorative background glows */}
      <div className="absolute top-[-10%] left-[-10%] w-64 h-64 bg-blue-400/10 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute bottom-[-5%] right-[-5%] w-72 h-72 bg-purple-400/10 rounded-full blur-3xl pointer-events-none"></div>

      <div className="text-center mb-10 z-10">
        <h2 className="text-3xl font-black text-slate-800 tracking-tight mb-2">Scan Receipt</h2>
        <p className="text-slate-500 font-medium">Auto-extract data with smart OCR</p>
      </div>

      <div 
        onClick={triggerUpload}
        className="w-full aspect-[3/4] max-w-[320px] relative rounded-[40px] flex flex-col items-center justify-center gap-6 cursor-pointer group z-10 transition-transform hover:scale-[1.02] active:scale-[0.98] duration-300"
      >
        {/* Animated Dashed Border using SVGs for premium look */}
        <div className="absolute inset-0 border-[3px] border-dashed border-blue-200/60 rounded-[40px] bg-gradient-to-b from-blue-50/50 to-white/50 group-hover:border-blue-400/50 group-hover:bg-blue-50/80 transition-all duration-500"></div>

        {/* Center Target Box */}
        <div className="absolute inset-8 border border-blue-100 rounded-[24px] opacity-50 flex items-center justify-center pointer-events-none">
          <ScanLine size={120} className="text-blue-100 stroke-[1]" />
        </div>

        <div className="relative z-10 w-24 h-24 bg-white rounded-full shadow-[0_8px_30px_rgb(59,130,246,0.15)] flex items-center justify-center text-blue-600 group-hover:shadow-[0_15px_40px_rgb(59,130,246,0.25)] transition-shadow duration-500">
          <Camera size={40} strokeWidth={2} />
        </div>
        
        <div className="relative z-10 text-center px-8">
          <p className="text-lg font-bold text-slate-700 mb-1">Tap to capture</p>
          <p className="text-sm font-medium text-slate-400">Position bill within the frame</p>
        </div>
      </div>
      
      <input 
        type="file" 
        ref={fileInputRef} 
        onChange={handleFileChange} 
        accept="image/*" 
        className="hidden" 
        capture="environment"
      />

      <button 
        onClick={triggerUpload}
        className="mt-12 z-10 flex items-center gap-2.5 bg-slate-800 hover:bg-slate-900 text-white px-8 py-4 rounded-full font-bold shadow-[0_10px_25px_rgb(30,41,59,0.2)] active:scale-[0.96] transition-all duration-300"
      >
        <ImagePlus size={22} />
        Choose from Library
      </button>
    </div>
  );
};

export default Capture;
